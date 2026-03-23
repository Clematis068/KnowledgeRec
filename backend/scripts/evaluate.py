"""
消融实验评估脚本 (Masked Temporal Split)
评估指标: Precision@K, Recall@K, NDCG@K, HitRate@K + 多样性指标 (Coverage, Entropy, ILS)
消融配置: 单通道 / 双通道组合 / 三路组合 / 完整六路融合 / GBDT精排

评估方法: 全局时间切分 + 行为屏蔽——按行为时间 80/20 分位确定 cutoff，
cutoff 之后的行为从 MySQL 中临时删除（让召回引擎只看到训练期数据），
cutoff 之后的 like/favorite 作为 ground truth。
评估结束后恢复所有被删除的行为记录。

用法: cd backend && uv run python -m scripts.evaluate
"""
import csv
import math
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.models.user import User
from app.services.recommendation import RecommendationEngine, _batch_load_posts
from app.services.recommendation.feature_extractor import FeatureExtractor
from app.services.recommendation.ranker import GBDTRanker, MODEL_PATH


# ─── 消融实验配置 ───
# 单路
ABLATION_CONFIGS = {
    "CF_only":          {'cf': 1.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    "Swing_only":       {'cf': 0.0, 'swing': 1.0, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    "Graph_only":       {'cf': 0.0, 'swing': 0.0, 'graph': 1.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    "Semantic_only":    {'cf': 0.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 1.0, 'knowledge': 0.0, 'hot': 0.0},
    "Knowledge_only":   {'cf': 0.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 1.0, 'hot': 0.0},
    "Hot_only":         {'cf': 0.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 1.0},
    # 双路组合
    "CF+Swing":         {'cf': 0.5, 'swing': 0.5, 'graph': 0.0, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    "CF+Graph":         {'cf': 0.5, 'swing': 0.0, 'graph': 0.5, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    "CF+Semantic":      {'cf': 0.5, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.5, 'knowledge': 0.0, 'hot': 0.0},
    "Graph+Semantic":   {'cf': 0.0, 'swing': 0.0, 'graph': 0.5, 'semantic': 0.5, 'knowledge': 0.0, 'hot': 0.0},
    # 三路组合
    "CF+Graph+Sem":     {'cf': 0.34, 'swing': 0.0, 'graph': 0.33, 'semantic': 0.33, 'knowledge': 0.0, 'hot': 0.0},
    "CF+Swing+Graph":   {'cf': 0.34, 'swing': 0.33, 'graph': 0.33, 'semantic': 0.0, 'knowledge': 0.0, 'hot': 0.0},
    # 完整六路融合（与 active 阶段权重一致）
    "Full_Fusion":      {'cf': 0.28, 'swing': 0.08, 'graph': 0.22, 'semantic': 0.20, 'knowledge': 0.12, 'hot': 0.10},
    # GBDT 精排（weights=None 触发 GBDT 路径）
    "GBDT_Ranking":     None,
}

K_VALUES = [5, 10, 20]
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "evaluation")


# ─── Baseline 推荐方法 ───

def baseline_random(user_id, all_post_ids, interacted_ids, top_n):
    """随机推荐：从未交互帖子中随机抽取"""
    pool = [pid for pid in all_post_ids if pid not in interacted_ids]
    return random.sample(pool, min(top_n, len(pool)))


def baseline_popular(user_id, post_popularity, interacted_ids, top_n):
    """热门推荐：按全局交互次数降序"""
    ranked = sorted(post_popularity.items(), key=lambda x: -x[1])
    return [pid for pid, _ in ranked if pid not in interacted_ids][:top_n]


def baseline_user_cf(user_id, user_item_matrix, top_n):
    """传统 UserCF：基于用户-用户余弦相似度推荐"""
    if user_id not in user_item_matrix:
        return []

    target_items = user_item_matrix[user_id]
    similarities = []

    for other_uid, other_items in user_item_matrix.items():
        if other_uid == user_id:
            continue
        common = target_items & other_items
        if not common:
            continue
        sim = len(common) / math.sqrt(len(target_items) * len(other_items))
        similarities.append((other_uid, sim))

    similarities.sort(key=lambda x: -x[1])
    top_neighbors = similarities[:20]

    scores = defaultdict(float)
    for neighbor_uid, sim in top_neighbors:
        for pid in user_item_matrix[neighbor_uid]:
            if pid not in target_items:
                scores[pid] += sim

    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return [pid for pid, _ in ranked[:top_n]]


def temporal_split_mask(train_ratio=0.8):
    """全局时间切分 + 行为屏蔽。

    1. 按行为时间的 train_ratio 分位确定 cutoff_time
    2. 保存 cutoff 后所有行为的完整数据
    3. 从 MySQL 中 DELETE cutoff 后的行为并 COMMIT（让并行召回线程可见）
    4. cutoff 后的 like/favorite 帖子作为 ground truth

    返回 (cutoff_time, test_set, train_interacted, hidden_rows)
      test_set:          {user_id: {'post_ids': set}}
      train_interacted:  {user_id: set(post_ids)}
      hidden_rows:       list[dict] —— 被删除行为的原始数据，用于恢复
    """
    print("全局时间切分 + 行为屏蔽...")

    # 取全部行为按时间排序，找分位点
    all_times = db.session.execute(
        db.select(UserBehavior.created_at).order_by(UserBehavior.created_at)
    ).scalars().all()
    if not all_times:
        return None, {}, {}, []

    split_idx = int(len(all_times) * train_ratio)
    cutoff_time = all_times[split_idx]
    print(f"  行为总数: {len(all_times)}")
    print(f"  cutoff 时间: {cutoff_time} (前 {split_idx} 条为训练集)")

    # 构建每个用户 cutoff 前已交互的帖子集合
    train_behaviors = db.session.scalars(
        db.select(UserBehavior).filter(UserBehavior.created_at <= cutoff_time)
    ).all()
    train_interacted = defaultdict(set)
    for b in train_behaviors:
        train_interacted[b.user_id].add(b.post_id)

    # 读取 cutoff 后的全部行为，保存为 dict 备份
    post_cutoff = db.session.scalars(
        db.select(UserBehavior).filter(UserBehavior.created_at > cutoff_time)
    ).all()

    hidden_rows = []
    test_set = defaultdict(set)
    for b in post_cutoff:
        hidden_rows.append({
            'id': b.id, 'user_id': b.user_id, 'post_id': b.post_id,
            'behavior_type': b.behavior_type, 'comment_text': b.comment_text,
            'parent_id': b.parent_id, 'duration': b.duration,
            'created_at': b.created_at,
        })
        if b.behavior_type in ('like', 'favorite'):
            test_set[b.user_id].add(b.post_id)

    # 过滤：测试集至少 2 个正样本的用户才纳入
    test_set = {uid: {'post_ids': pids} for uid, pids in test_set.items() if len(pids) >= 2}

    total_test = sum(len(v['post_ids']) for v in test_set.values())
    print(f"  测试用户数: {len(test_set)}")
    print(f"  测试帖子总数: {total_test}")
    if test_set:
        print(f"  平均每用户测试帖子: {total_test / len(test_set):.1f}")

    # ── 屏蔽：从 DB 中删除 cutoff 后行为 ──
    # 先清除 parent_id 引用（避免 FK 约束报错）
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
    print(f"  已屏蔽 {deleted} 条 cutoff 后行为（评估结束后恢复）")

    return cutoff_time, test_set, dict(train_interacted), hidden_rows


def restore_behaviors(hidden_rows):
    """恢复被屏蔽的行为记录。"""
    if not hidden_rows:
        return
    print(f"\n恢复 {len(hidden_rows)} 条被屏蔽的行为...")
    # 分批插入，避免单次 INSERT 过大
    batch_size = 500
    for start in range(0, len(hidden_rows), batch_size):
        batch = hidden_rows[start:start + batch_size]
        db.session.execute(db.insert(UserBehavior), batch)
    db.session.commit()
    # 验证
    total = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
    print(f"  恢复完成，当前行为总数: {total}")


def precision_at_k(recommended, relevant, k):
    rec_k = set(recommended[:k])
    if not rec_k:
        return 0.0
    return len(rec_k & relevant) / k


def recall_at_k(recommended, relevant, k):
    rec_k = set(recommended[:k])
    if not relevant:
        return 0.0
    return len(rec_k & relevant) / len(relevant)


def ndcg_at_k(recommended, relevant, k):
    dcg = 0.0
    for i, item in enumerate(recommended[:k]):
        if item in relevant:
            dcg += 1.0 / math.log2(i + 2)

    ideal_len = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_len))
    return dcg / idcg if idcg > 0 else 0.0


def hitrate_at_k(recommended, relevant, k):
    """HitRate@K：Top-K 中是否至少命中 1 个正样本（0 或 1）"""
    rec_k = set(recommended[:k])
    return 1.0 if rec_k & relevant else 0.0


# ─── 多样性指标 ───

def coverage_at_k(recommended_ids, k, post_domain_map, total_domains):
    """领域覆盖率：Top-K 推荐覆盖了多少个不同领域 / 总领域数"""
    rec_k = recommended_ids[:k]
    domains_hit = set()
    for pid in rec_k:
        did = post_domain_map.get(pid)
        if did is not None:
            domains_hit.add(did)
    return len(domains_hit) / total_domains if total_domains > 0 else 0.0


def entropy_at_k(recommended_ids, k, post_domain_map):
    """领域熵：推荐列表的领域分布均匀度，越高越多样"""
    rec_k = recommended_ids[:k]
    domain_list = [post_domain_map.get(pid) for pid in rec_k if post_domain_map.get(pid) is not None]
    if not domain_list:
        return 0.0
    counts = Counter(domain_list)
    total = len(domain_list)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


def ils_at_k(recommended_ids, k, post_domain_map):
    """ILS (Intra-List Similarity): 列表内相似度，越低越多样。
    用领域是否相同作为相似度（同领域=1，不同=0），计算所有对的平均值。
    """
    rec_k = recommended_ids[:k]
    domains = [post_domain_map.get(pid) for pid in rec_k]
    n = len(domains)
    if n < 2:
        return 0.0
    same_count = 0
    pair_count = 0
    for i in range(n):
        for j in range(i + 1, n):
            pair_count += 1
            if domains[i] is not None and domains[i] == domains[j]:
                same_count += 1
    return same_count / pair_count if pair_count > 0 else 0.0


def evaluate_config(config_name, weights, test_set, train_interacted, k_values, engine,
                    post_domain_map, total_domains, recall_cache=None):
    """评估单个消融配置（行为已屏蔽，召回引擎只看到训练期数据）。
    recall_cache: 可选，{user_id: results_map} 预缓存的召回结果，避免重复召回。
    返回 (avg_metrics, per_user_metrics)。
    """
    metrics = {k: {'precision': [], 'recall': [], 'ndcg': [], 'hitrate': [],
                    'coverage': [], 'entropy': [], 'ils': []} for k in k_values}
    per_user = {}  # {user_id: {k: {metric: value}}}

    user_ids = list(test_set.keys())
    max_k = max(k_values)

    for i, user_id in enumerate(user_ids):
        relevant = test_set[user_id]['post_ids']
        exclude = list(train_interacted.get(user_id, set()))

        try:
            if recall_cache is not None and user_id in recall_cache:
                # 使用缓存的召回结果，只做融合 + 后处理
                results_map = recall_cache[user_id]
                excluded_ids = set(int(pid) for pid in exclude if str(pid).isdigit())
                if weights is None and engine.ranker.is_available():
                    final_results, _ = engine._gbdt_ranking_pipeline(
                        user_id, results_map, max_k, excluded_ids, None, True,
                    )
                else:
                    final_results, _ = engine._legacy_fusion_pipeline(
                        user_id, results_map, max_k, excluded_ids, None, weights, True, True,
                    )
                recommended = [r['post_id'] for r in final_results]
            else:
                results = engine.recommend(
                    user_id, top_n=max_k, enable_llm=False, weights=weights,
                    exclude_post_ids=exclude,
                )
                recommended = [r['post_id'] for r in results]
        except Exception as e:
            print(f"  [{config_name}] user {user_id} error: {e}")
            recommended = []

        user_metrics = {}
        for k in k_values:
            p = precision_at_k(recommended, relevant, k)
            r = recall_at_k(recommended, relevant, k)
            n = ndcg_at_k(recommended, relevant, k)
            h = hitrate_at_k(recommended, relevant, k)
            metrics[k]['precision'].append(p)
            metrics[k]['recall'].append(r)
            metrics[k]['ndcg'].append(n)
            metrics[k]['hitrate'].append(h)
            metrics[k]['coverage'].append(coverage_at_k(recommended, k, post_domain_map, total_domains))
            metrics[k]['entropy'].append(entropy_at_k(recommended, k, post_domain_map))
            metrics[k]['ils'].append(ils_at_k(recommended, k, post_domain_map))
            user_metrics[k] = {'precision': p, 'recall': r, 'ndcg': n, 'hitrate': h}
        per_user[user_id] = user_metrics

        if (i + 1) % 50 == 0:
            print(f"  [{config_name}] 进度: {i + 1}/{len(user_ids)}")

    avg_metrics = {}
    for k in k_values:
        n = len(metrics[k]['precision'])
        if n == 0:
            avg_metrics[k] = {'precision': 0, 'recall': 0, 'ndcg': 0, 'hitrate': 0,
                              'coverage': 0, 'entropy': 0, 'ils': 0}
        else:
            avg_metrics[k] = {
                'precision': sum(metrics[k]['precision']) / n,
                'recall': sum(metrics[k]['recall']) / n,
                'ndcg': sum(metrics[k]['ndcg']) / n,
                'hitrate': sum(metrics[k]['hitrate']) / n,
                'coverage': sum(metrics[k]['coverage']) / n,
                'entropy': sum(metrics[k]['entropy']) / n,
                'ils': sum(metrics[k]['ils']) / n,
            }

    return avg_metrics, per_user


# ─── 报告输出 ───

def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(header)
        writer.writerows(rows)


def markdown_table(headers, rows):
    if not rows:
        return "| 空 |\n| --- |\n| 无数据 |\n"
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines) + "\n"


def build_ablation_rows(all_results, k_values):
    rows = []
    for config_name, avg in all_results.items():
        for k in k_values:
            m = avg[k]
            rows.append([
                config_name, k,
                round(m['precision'], 6),
                round(m['recall'], 6),
                round(m['ndcg'], 6),
                round(m['hitrate'], 6),
                round(m['coverage'], 6),
                round(m['entropy'], 6),
                round(m['ils'], 6),
            ])
    return rows


def write_reports(all_results, k_values, test_user_count, cutoff_time):
    os.makedirs(REPORT_DIR, exist_ok=True)

    rows = build_ablation_rows(all_results, k_values)
    csv_header = ["config", "k", "precision", "recall", "ndcg", "hitrate", "coverage", "entropy", "ils"]

    # CSV
    write_csv(os.path.join(REPORT_DIR, "ablation_metrics.csv"), csv_header, rows)

    # Markdown 报告
    md_headers = ["配置", "K", "P@K", "R@K", "NDCG@K", "HR@K", "Coverage", "Entropy", "ILS↓"]
    content = [
        "# 消融实验评估报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 测试用户数：{test_user_count}",
        f"- K 值：{k_values}",
        f"- 消融配置数：{len(all_results)}",
        f"- 评估方法：Masked Temporal Split（全局时间切分 + 行为屏蔽，cutoff = {cutoff_time}）",
        "",
        "## 指标表",
        "",
        markdown_table(md_headers, rows),
        "## 配置说明",
        "",
        "### Baseline",
        "- `[B] Random`：从未交互帖子中随机推荐",
        "- `[B] Popular`：按全局交互热度降序推荐",
        "- `[B] UserCF`：传统 User-Based CF（余弦相似度 + Top-20 近邻）",
        "",
        "### 消融配置",
        "- 单路：仅启用 1 个召回通道，其余权重为 0",
        "- 双路：两个通道等权 0.5",
        "- 三路：三个通道近似等权",
        "- Full_Fusion：六路完整融合（与 active 阶段权重一致）",
        "- GBDT_Ranking：6路召回 → GBDT精排（weights=None 自动走 GBDT 路径）",
        "",
        "## 指标说明",
        "",
        "### 准确率指标",
        "- `P@K`：Top-K 推荐中与测试集匹配的比例（精确率）",
        "- `R@K`：测试集中被 Top-K 命中的比例（召回率）",
        "- `NDCG@K`：考虑排序位置的归一化折扣累计增益",
        "- `HR@K`：HitRate，Top-K 中至少命中 1 个正样本的用户比例",
        "",
        "### 多样性指标",
        "- `Coverage`：推荐列表覆盖的领域数 / 总领域数（越高越好）",
        "- `Entropy`：推荐列表领域分布的信息熵（越高越均匀多样）",
        "- `ILS↓`：列表内相似度 Intra-List Similarity（越低越多样）",
        "",
        "## 评估方法说明",
        "",
        "采用 Masked Temporal Split（全局时间切分 + 行为屏蔽）：",
        "1. 按行为时间 80/20 分位确定 cutoff_time",
        "2. 将 cutoff 后的所有行为从 MySQL 中临时删除（让召回引擎只看到训练期数据）",
        "3. cutoff 后的 like/favorite 帖子作为 ground truth",
        "4. 推荐时通过 exclude_post_ids 排除训练期已交互帖子",
        "5. 评估结束后恢复所有被删除的行为",
        "",
        "相比原始 Temporal Split，此方法解决了召回引擎内部排除已交互帖子导致测试集",
        "无法被召回的问题（CF/Swing/Graph 引擎从 DB 读取用户行为构建候选，",
        "若测试期行为仍在 DB 中则测试帖子会被引擎自身过滤掉）。",
        "",
    ]
    with open(os.path.join(REPORT_DIR, "ablation_report.md"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(content))


def _classify_user_stage(user_id, train_interacted):
    """根据训练期交互数分层。"""
    n = len(train_interacted.get(user_id, set()))
    if n == 0:
        return 'cold'
    if n < 15:
        return 'warm'
    return 'active'


def print_stratified_results(all_per_user, train_interacted, k_values):
    """按用户活跃度分组输出关键配置的 HR@K。"""
    key_configs = ["CF_only", "Swing_only", "CF+Swing", "Semantic_only",
                   "Knowledge_only", "Graph_only", "Full_Fusion", "GBDT_Ranking"]
    key_configs = [c for c in key_configs if c in all_per_user]

    # 分层
    stages = {'cold': [], 'warm': [], 'active': []}
    sample_config = next(iter(all_per_user.values()))
    for uid in sample_config:
        stage = _classify_user_stage(uid, train_interacted)
        stages[stage].append(uid)

    print(f"\n{'=' * 100}")
    print(f"分层分析 (cold: {len(stages['cold'])}, warm: {len(stages['warm'])}, active: {len(stages['active'])})")
    print(f"{'=' * 100}")

    for k in k_values:
        print(f"\n--- HR@{k} 分层 ---")
        print(f"{'配置':<20} {'Cold':<10} {'Warm':<10} {'Active':<10} {'Overall':<10}")
        print("-" * 60)
        for config_name in key_configs:
            per_user = all_per_user[config_name]
            stage_hr = {}
            for stage_name, uids in stages.items():
                if not uids:
                    stage_hr[stage_name] = 0.0
                    continue
                hits = [per_user[uid][k]['hitrate'] for uid in uids if uid in per_user]
                stage_hr[stage_name] = sum(hits) / len(hits) if hits else 0.0
            all_hits = [per_user[uid][k]['hitrate'] for uid in per_user]
            overall = sum(all_hits) / len(all_hits) if all_hits else 0.0
            print(f"{config_name:<20} {stage_hr['cold']:<10.4f} {stage_hr['warm']:<10.4f} "
                  f"{stage_hr['active']:<10.4f} {overall:<10.4f}")

    print(f"{'=' * 100}")


def write_stratified_report(all_per_user, train_interacted, k_values):
    """输出分层分析 CSV。"""
    key_configs = ["CF_only", "Swing_only", "CF+Swing", "Semantic_only",
                   "Knowledge_only", "Graph_only", "Full_Fusion", "GBDT_Ranking"]
    key_configs = [c for c in key_configs if c in all_per_user]

    stages = {'cold': [], 'warm': [], 'active': []}
    sample_config = next(iter(all_per_user.values()))
    for uid in sample_config:
        stage = _classify_user_stage(uid, train_interacted)
        stages[stage].append(uid)

    rows = []
    for config_name in key_configs:
        per_user = all_per_user[config_name]
        for k in k_values:
            for stage_name, uids in stages.items():
                if not uids:
                    continue
                hits = [per_user[uid][k]['hitrate'] for uid in uids if uid in per_user]
                precs = [per_user[uid][k]['precision'] for uid in uids if uid in per_user]
                ndcgs = [per_user[uid][k]['ndcg'] for uid in uids if uid in per_user]
                rows.append([
                    config_name, k, stage_name, len(uids),
                    round(sum(precs) / len(precs), 6) if precs else 0,
                    round(sum(ndcgs) / len(ndcgs), 6) if ndcgs else 0,
                    round(sum(hits) / len(hits), 6) if hits else 0,
                ])

    csv_path = os.path.join(REPORT_DIR, "stratified_metrics.csv")
    write_csv(csv_path, ["config", "k", "stage", "n_users", "precision", "ndcg", "hitrate"], rows)
    print(f"分层分析已写入: {csv_path}")


def print_results(all_results, k_values):
    print("\n" + "=" * 140)
    print(f"{'配置':<20}", end="")
    for k in k_values:
        print(f"| P@{k:<3} R@{k:<3} NDCG@{k:<3} HR@{k:<3} Cov   Ent   ILS  ", end="")
    print()
    print("-" * 140)

    for config_name, avg in all_results.items():
        print(f"{config_name:<20}", end="")
        for k in k_values:
            m = avg[k]
            print(f"| {m['precision']:.4f} {m['recall']:.4f} {m['ndcg']:.4f} {m['hitrate']:.3f} "
                  f"{m['coverage']:.3f} {m['entropy']:.3f} {m['ils']:.3f} ", end="")
        print()

    print("=" * 140)


def evaluate_baseline(baseline_name, baseline_fn, test_set, k_values, post_domain_map, total_domains):
    """评估 baseline 方法"""
    metrics = {k: {'precision': [], 'recall': [], 'ndcg': [], 'hitrate': [],
                    'coverage': [], 'entropy': [], 'ils': []} for k in k_values}

    for user_id, test_info in test_set.items():
        relevant = test_info['post_ids']
        try:
            recommended = baseline_fn(user_id)
        except Exception as e:
            print(f"  [{baseline_name}] user {user_id} error: {e}")
            recommended = []

        for k in k_values:
            metrics[k]['precision'].append(precision_at_k(recommended, relevant, k))
            metrics[k]['recall'].append(recall_at_k(recommended, relevant, k))
            metrics[k]['ndcg'].append(ndcg_at_k(recommended, relevant, k))
            metrics[k]['hitrate'].append(hitrate_at_k(recommended, relevant, k))
            metrics[k]['coverage'].append(coverage_at_k(recommended, k, post_domain_map, total_domains))
            metrics[k]['entropy'].append(entropy_at_k(recommended, k, post_domain_map))
            metrics[k]['ils'].append(ils_at_k(recommended, k, post_domain_map))

    avg_metrics = {}
    for k in k_values:
        n = len(metrics[k]['precision'])
        if n == 0:
            avg_metrics[k] = {'precision': 0, 'recall': 0, 'ndcg': 0, 'hitrate': 0,
                              'coverage': 0, 'entropy': 0, 'ils': 0}
        else:
            avg_metrics[k] = {
                'precision': sum(metrics[k]['precision']) / n,
                'recall': sum(metrics[k]['recall']) / n,
                'ndcg': sum(metrics[k]['ndcg']) / n,
                'hitrate': sum(metrics[k]['hitrate']) / n,
                'coverage': sum(metrics[k]['coverage']) / n,
                'entropy': sum(metrics[k]['entropy']) / n,
                'ils': sum(metrics[k]['ils']) / n,
            }
    return avg_metrics


def retrain_gbdt_on_train_data(engine):
    """在训练期数据上重训 GBDT（嵌套时间切分，避免 data leakage）。

    主评估已将数据切为 [0, main_cutoff](DB) / [main_cutoff, end](masked)。
    此函数在训练期 [0, main_cutoff] 内再做 80/20 切分：
      - 召回只看 [0, gbdt_cutoff]
      - 正样本标签 = [gbdt_cutoff, main_cutoff] 中的 like/favorite
    训练完后恢复内层 mask，使评估阶段能看到完整训练期数据。
    """
    import numpy as np
    print("\n--- 在训练期数据上重训 GBDT（嵌套时间切分） ---")

    RECALL_TOP_K = 50

    # ── 内层时间切分 ──
    all_times = db.session.execute(
        db.select(UserBehavior.created_at).order_by(UserBehavior.created_at)
    ).scalars().all()
    if not all_times:
        print("  训练期无行为，跳过")
        return None

    inner_split_idx = int(len(all_times) * 0.8)
    gbdt_cutoff = all_times[inner_split_idx]
    print(f"  内层 cutoff: {gbdt_cutoff} (前 {inner_split_idx} 条驱动召回)")

    # 读取 [gbdt_cutoff, main_cutoff] 的行为作为标签 + 备份
    inner_post_cutoff = db.session.scalars(
        db.select(UserBehavior).filter(UserBehavior.created_at > gbdt_cutoff)
    ).all()

    inner_hidden_rows = []
    gbdt_future_positives = defaultdict(set)
    for b in inner_post_cutoff:
        inner_hidden_rows.append({
            'id': b.id, 'user_id': b.user_id, 'post_id': b.post_id,
            'behavior_type': b.behavior_type, 'comment_text': b.comment_text,
            'parent_id': b.parent_id, 'duration': b.duration,
            'created_at': b.created_at,
        })
        if b.behavior_type in ('like', 'favorite'):
            gbdt_future_positives[b.user_id].add(b.post_id)

    if not gbdt_future_positives:
        print("  内层切分无未来正样本，跳过")
        return None

    # 内层 mask
    db.session.execute(
        db.text(
            "UPDATE user_behavior SET parent_id = NULL "
            "WHERE created_at > :cutoff AND parent_id IS NOT NULL"
        ),
        {"cutoff": gbdt_cutoff},
    )
    inner_deleted = db.session.execute(
        db.text("DELETE FROM user_behavior WHERE created_at > :cutoff"),
        {"cutoff": gbdt_cutoff},
    ).rowcount
    db.session.commit()
    print(f"  内层屏蔽 {inner_deleted} 条，有未来正样本用户: {len(gbdt_future_positives)}")

    try:
        extractor = FeatureExtractor()
        ranker = GBDTRanker()

        # 获取内层训练期行为足够的用户
        rows = db.session.execute(
            db.select(
                UserBehavior.user_id,
                db.func.count().label("cnt"),
            )
            .filter(UserBehavior.behavior_type.in_(["browse", "like", "comment", "favorite"]))
            .group_by(UserBehavior.user_id)
            .having(db.func.count() >= 5)
        ).all()
        eligible = {row[0] for row in rows}
        user_ids = [uid for uid in gbdt_future_positives if uid in eligible]
        print(f"  GBDT 训练用户数: {len(user_ids)}")

        all_X, all_y = [], []
        skipped = 0

        for idx, user_id in enumerate(user_ids):
            try:
                results_map = engine._parallel_recall(user_id, enable_llm=False)
            except Exception:
                skipped += 1
                continue

            candidate_ids = set()
            for scores in results_map.values():
                top_ids = sorted(scores, key=scores.get, reverse=True)[:RECALL_TOP_K]
                candidate_ids.update(top_ids)
            if not candidate_ids:
                skipped += 1
                continue

            user_future_pos = gbdt_future_positives[user_id]
            pos_in_candidates = candidate_ids & user_future_pos
            neg_in_candidates = candidate_ids - user_future_pos

            if not pos_in_candidates:
                skipped += 1
                continue

            neg_sample_size = min(len(neg_in_candidates), len(pos_in_candidates) * 3)
            neg_sampled = set(random.sample(list(neg_in_candidates), neg_sample_size)) if neg_sample_size > 0 else set()

            sample_ids = list(pos_in_candidates | neg_sampled)
            labels = [1 if pid in pos_in_candidates else 0 for pid in sample_ids]

            recall_scores = {
                pid: {name: scores.get(pid, 0.0) for name, scores in results_map.items()}
                for pid in sample_ids
            }
            post_cache = _batch_load_posts(sample_ids)
            extractor.warm_user_cache(user_id, logic_engine=engine.logic)
            context = engine._resolve_context(user_id)
            features = extractor.extract_batch(user_id, sample_ids, recall_scores, context, post_cache)
            extractor.clear_cache()

            all_X.extend(features)
            all_y.extend(labels)

            if (idx + 1) % 20 == 0:
                print(f"  进度: {idx + 1}/{len(user_ids)} | 样本: {len(all_y)}")

        if not all_y or sum(all_y) == 0:
            print("  无正样本，跳过 GBDT 训练")
            return None

        pos_total = sum(all_y)
        print(f"  样本: {len(all_y)} (正: {pos_total}, 负: {len(all_y) - pos_total})")

        metrics = ranker.train(all_X, all_y)
        ranker.save()
        print(f"  AUC: {metrics['auc']:.4f}, Accuracy: {metrics['accuracy']:.4f}")

        engine.ranker.load()
        return metrics

    finally:
        # ── 恢复内层 mask，使评估阶段看到完整训练期数据 ──
        if inner_hidden_rows:
            batch_size = 500
            for start in range(0, len(inner_hidden_rows), batch_size):
                batch = inner_hidden_rows[start:start + batch_size]
                db.session.execute(db.insert(UserBehavior), batch)
            db.session.commit()
            restored = db.session.scalar(db.select(db.func.count()).select_from(UserBehavior))
            print(f"  内层恢复完成，当前行为数: {restored}")


def main():
    random.seed(42)
    app = create_app()
    with app.app_context():
        cutoff_time, test_set, train_interacted, hidden_rows = temporal_split_mask()
        if not test_set:
            restore_behaviors(hidden_rows)
            print("测试集为空，请先生成数据")
            return

        # 备份原始模型
        original_model_backup = None
        if os.path.isfile(MODEL_PATH):
            with open(MODEL_PATH, "rb") as f:
                original_model_backup = f.read()

        try:
            # 构建 post_id → domain_id 映射（多样性指标用）
            post_rows = db.session.execute(db.select(Post.id, Post.domain_id)).all()
            post_domain_map = {pid: did for pid, did in post_rows}
            all_post_ids = list(post_domain_map.keys())
            total_domains = len(set(did for did in post_domain_map.values() if did is not None))
            print(f"帖子总数: {len(post_domain_map)}, 领域总数: {total_domains}")

            # 构建 baseline 所需数据结构（仅用 cutoff 前行为，即当前 DB 中全部行为）
            train_behaviors = db.session.scalars(db.select(UserBehavior)).all()
            post_popularity = Counter(b.post_id for b in train_behaviors)
            user_item_matrix = defaultdict(set)
            for b in train_behaviors:
                user_item_matrix[b.user_id].add(b.post_id)

            engine = RecommendationEngine()

            # 在训练期数据上重训 GBDT（解决 data leakage）
            retrain_metrics = retrain_gbdt_on_train_data(engine)

            max_k = max(K_VALUES)

            print(f"\n===== 消融实验评估 (Masked Temporal Split) =====")
            print(f"测试用户: {len(test_set)}")
            print(f"K 值: {K_VALUES}")

            all_results = {}

            # ── Baseline 评估 ──
            print("\n--- Baseline 方法 ---")

            print("评估: Random")
            all_results["[B] Random"] = evaluate_baseline(
                "Random",
                lambda uid: baseline_random(uid, all_post_ids, train_interacted.get(uid, set()), max_k),
                test_set, K_VALUES, post_domain_map, total_domains,
            )

            print("评估: Popular")
            all_results["[B] Popular"] = evaluate_baseline(
                "Popular",
                lambda uid: baseline_popular(uid, post_popularity, train_interacted.get(uid, set()), max_k),
                test_set, K_VALUES, post_domain_map, total_domains,
            )

            print("评估: UserCF")
            all_results["[B] UserCF"] = evaluate_baseline(
                "UserCF",
                lambda uid: baseline_user_cf(uid, user_item_matrix, max_k),
                test_set, K_VALUES, post_domain_map, total_domains,
            )

            # ── 消融实验 ──
            # 核心优化：每用户只召回一次，所有配置复用召回结果
            print("\n--- 预缓存召回结果（每用户只召回一次） ---")
            recall_cache = {}  # {user_id: results_map}
            user_ids = list(test_set.keys())
            for i, user_id in enumerate(user_ids):
                try:
                    results_map = engine._parallel_recall(user_id, enable_llm=False)
                    recall_cache[user_id] = results_map
                except Exception as e:
                    print(f"  user {user_id} recall error: {e}")
                if (i + 1) % 50 == 0:
                    print(f"  召回进度: {i + 1}/{len(user_ids)}")
            print(f"  召回缓存完成: {len(recall_cache)} 用户")

            print("\n--- 消融实验 ---")
            all_per_user = {}  # {config_name: {user_id: {k: metrics}}}
            for config_name, weights in ABLATION_CONFIGS.items():
                print(f"评估: {config_name}")
                avg, per_user = evaluate_config(
                    config_name, weights, test_set, train_interacted,
                    K_VALUES, engine, post_domain_map, total_domains,
                    recall_cache=recall_cache,
                )
                all_results[config_name] = avg
                all_per_user[config_name] = per_user

            print_results(all_results, K_VALUES)

            # ── 分层分析 ──
            print_stratified_results(all_per_user, train_interacted, K_VALUES)

            write_reports(all_results, K_VALUES, len(test_set), cutoff_time)
            write_stratified_report(all_per_user, train_interacted, K_VALUES)
            print(f"\n报告已写入: {REPORT_DIR}")

        finally:
            restore_behaviors(hidden_rows)
            # 恢复原始 GBDT 模型
            if original_model_backup is not None:
                with open(MODEL_PATH, "wb") as f:
                    f.write(original_model_backup)
                print("已恢复原始 GBDT 模型")


if __name__ == '__main__':
    main()
