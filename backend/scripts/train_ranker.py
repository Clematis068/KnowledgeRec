"""
训练 GBDT 精排模型（Temporal Split 版）。

核心思路——时间回溯：
  1. 按行为时间 80/20 切分，将 cutoff 后的行为从 DB 中临时删除
  2. 召回引擎只看 cutoff 前的数据，排除 cutoff 前已交互的帖子
  3. cutoff 后用户 like/favorite 的帖子自然出现在召回候选中 → 正样本
  4. 召回候选中用户未交互的帖子 → 负样本（降采样 1:3）
  5. 提取 18 维特征，训练 GBDT
  6. 训练完毕后恢复所有被删除的行为

这完美模拟了线上场景：召回给用户推了一批新帖子，有些他后来喜欢了（正），
有些他没兴趣（负）。

用法: cd backend && uv run python -m scripts.train_ranker
"""
import os
import random
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.services.recommendation import RecommendationEngine, _batch_load_posts
from app.services.recommendation.feature_extractor import FeatureExtractor
from app.services.recommendation.ranker import GBDTRanker

RECALL_TOP_K = 50  # 每路召回取 top-K，与线上 serving 一致


def temporal_split_mask(train_ratio=0.8):
    """全局时间切分 + 行为屏蔽。

    1. 按行为时间的 train_ratio 分位确定 cutoff_time
    2. 从 DB 中 DELETE cutoff 后的行为（让召回引擎只看训练期数据）
    3. cutoff 后的 like/favorite 作为正样本标签

    返回 (cutoff_time, future_positives, hidden_rows)
      future_positives: {user_id: set(post_id)} —— cutoff 后 like/favorite
      hidden_rows:      list[dict] —— 被删除行为的原始数据，用于恢复
    """
    print("时间切分 + 行为屏蔽...")

    all_times = db.session.execute(
        db.select(UserBehavior.created_at).order_by(UserBehavior.created_at)
    ).scalars().all()
    if not all_times:
        return None, {}, []

    split_idx = int(len(all_times) * train_ratio)
    cutoff_time = all_times[split_idx]
    print(f"  行为总数: {len(all_times)}")
    print(f"  cutoff: {cutoff_time} (前 {split_idx} 条为训练集)")

    # 读取 cutoff 后的全部行为，保存备份
    post_cutoff = db.session.scalars(
        db.select(UserBehavior).filter(UserBehavior.created_at > cutoff_time)
    ).all()

    hidden_rows = []
    future_positives = defaultdict(set)
    for b in post_cutoff:
        hidden_rows.append({
            'id': b.id, 'user_id': b.user_id, 'post_id': b.post_id,
            'behavior_type': b.behavior_type, 'comment_text': b.comment_text,
            'parent_id': b.parent_id, 'duration': b.duration,
            'created_at': b.created_at,
        })
        if b.behavior_type in ('like', 'favorite'):
            future_positives[b.user_id].add(b.post_id)

    # 从 DB 中删除 cutoff 后行为
    db.session.execute(
        db.text(
            "UPDATE user_behavior SET parent_id = NULL "
            "WHERE created_at > :cutoff AND parent_id IS NOT NULL"
        ),
        {"cutoff": cutoff_time},
    )
    deleted = db.session.execute(
        db.text("DELETE FROM user_behavior WHERE created_at > :cutoff"),
        {"cutoff": cutoff_time},
    ).rowcount
    db.session.commit()
    print(f"  已屏蔽 {deleted} 条 cutoff 后行为")
    print(f"  有未来正样本的用户数: {len(future_positives)}")

    return cutoff_time, dict(future_positives), hidden_rows


def restore_behaviors(hidden_rows):
    """恢复被屏蔽的行为记录。"""
    if not hidden_rows:
        return
    print(f"\n恢复 {len(hidden_rows)} 条被屏蔽的行为...")
    batch_size = 500
    for start in range(0, len(hidden_rows), batch_size):
        batch = hidden_rows[start:start + batch_size]
        db.session.execute(db.insert(UserBehavior), batch)
    db.session.commit()
    total = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
    print(f"  恢复完成，当前行为总数: {total}")


def get_eligible_users(min_behaviors=5):
    """返回当前 DB 中 behavior_count >= min_behaviors 的用户 ID 列表。"""
    rows = db.session.execute(
        db.select(
            UserBehavior.user_id,
            db.func.count().label("cnt"),
        )
        .filter(UserBehavior.behavior_type.in_(["browse", "like", "comment", "favorite"]))
        .group_by(UserBehavior.user_id)
        .having(db.func.count() >= min_behaviors)
    ).all()
    return [row[0] for row in rows]


def main():
    random.seed(42)
    np.random.seed(42)

    app = create_app()
    with app.app_context():
        # ── 1. 时间切分 ──
        cutoff_time, future_positives, hidden_rows = temporal_split_mask()
        if not future_positives:
            restore_behaviors(hidden_rows)
            print("没有未来正样本，无法训练。请检查数据。")
            return

        try:
            engine = RecommendationEngine()
            extractor = FeatureExtractor()
            ranker = GBDTRanker()

            # 只训练「有未来正样本」且「训练期行为足够」的用户
            eligible_users = set(get_eligible_users(min_behaviors=5))
            user_ids = [uid for uid in future_positives if uid in eligible_users]
            print(f"\n训练用户数: {len(user_ids)} (有未来正样本 且 训练期行为>=5)")

            all_X = []
            all_y = []
            skipped = 0
            total_pos = 0
            total_neg = 0

            for idx, user_id in enumerate(user_ids):
                # ── 2. 召回（只看 cutoff 前数据） ──
                try:
                    results_map = engine._parallel_recall(user_id, enable_llm=False)
                except Exception as e:
                    print(f"  用户 {user_id} 召回失败: {e}")
                    skipped += 1
                    continue

                # 每路取 top-K，合并候选
                candidate_ids = set()
                for scores in results_map.values():
                    top_ids = sorted(scores, key=scores.get, reverse=True)[:RECALL_TOP_K]
                    candidate_ids.update(top_ids)
                if not candidate_ids:
                    skipped += 1
                    continue

                # ── 3. 标注：未来交互 = 正样本 ──
                user_future_pos = future_positives[user_id]
                pos_in_candidates = candidate_ids & user_future_pos
                neg_in_candidates = candidate_ids - user_future_pos

                if not pos_in_candidates:
                    skipped += 1
                    continue

                # 负采样 1:3
                neg_sample_size = min(len(neg_in_candidates), len(pos_in_candidates) * 3)
                neg_sampled = set(random.sample(list(neg_in_candidates), neg_sample_size)) if neg_sample_size > 0 else set()

                sample_ids = list(pos_in_candidates | neg_sampled)
                labels = [1 if pid in pos_in_candidates else 0 for pid in sample_ids]
                total_pos += sum(labels)
                total_neg += len(labels) - sum(labels)

                # ── 4. 特征提取 ──
                recall_scores = {}
                for pid in sample_ids:
                    recall_scores[pid] = {
                        name: scores.get(pid, 0.0)
                        for name, scores in results_map.items()
                    }

                post_cache = _batch_load_posts(sample_ids)
                extractor.warm_user_cache(user_id, logic_engine=engine.logic)
                context = engine._resolve_context(user_id)
                features = extractor.extract_batch(
                    user_id, sample_ids, recall_scores, context, post_cache,
                )
                extractor.clear_cache()

                all_X.extend(features)
                all_y.extend(labels)

                if (idx + 1) % 20 == 0:
                    print(f"  进度: {idx + 1}/{len(user_ids)} | "
                          f"样本: {len(all_y)} (正: {total_pos}, 负: {total_neg})")

            # ── 5. 训练 ──
            print(f"\n跳过用户: {skipped}")
            print(f"总样本数: {len(all_y)}")
            if not all_y or sum(all_y) == 0:
                print("没有正样本，无法训练。请检查数据。")
                return

            print(f"正样本: {total_pos}, 负样本: {total_neg}, "
                  f"正比例: {total_pos / len(all_y):.3f}")

            print("\n开始训练 GBDT...")
            metrics = ranker.train(all_X, all_y)

            print(f"\n=== 训练结果 ===")
            print(f"AUC: {metrics['auc']:.4f}")
            print(f"Accuracy: {metrics['accuracy']:.4f}")
            print(f"训练集: {metrics['train_size']}, 验证集: {metrics['val_size']}")
            print(f"正比例 (训练): {metrics['positive_ratio_train']:.3f}, "
                  f"(验证): {metrics['positive_ratio_val']:.3f}")

            print(f"\n=== 特征重要性 (降序) ===")
            importance = metrics['feature_importance']
            for name, imp in sorted(importance.items(), key=lambda x: -x[1]):
                bar = "█" * int(imp * 100)
                print(f"  {name:<22s} {imp:.4f} {bar}")

            ranker.save()
            print(f"\n模型已保存")

        finally:
            # ── 6. 恢复行为 ──
            restore_behaviors(hidden_rows)


if __name__ == "__main__":
    main()
