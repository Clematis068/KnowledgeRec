"""
冷启动评估脚本：对比热门召回开启/关闭时，对新用户/低行为用户的召回影响。

指标说明：
1. Precision@K / Recall@K:
   把“与注册兴趣 tag 或 domain 匹配的帖子”视为伪相关集合 relevant。
2. HitRate@K:
   Top-K 中是否至少出现 1 条相关帖子。
3. InterestTagRecall@K:
   Top-K 覆盖了多少比例的注册兴趣标签，衡量新用户兴趣是否被召回到。

用法:
  cd backend && uv run python -m scripts.evaluate_cold_start
  cd backend && uv run python -m scripts.evaluate_cold_start --max-behaviors 0 --k 10 20
"""
import argparse
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.models.user import User
from app.services.recommendation import recommendation_engine


COMPARE_CONFIGS = {
    "without_hot": False,
    "with_hot": True,
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-behaviors", type=int, default=3, help="最多保留多少条行为，视作冷启动/低行为用户")
    parser.add_argument("--min-interest-tags", type=int, default=1, help="至少拥有多少个注册兴趣标签")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10, 20], help="评估的 K 值")
    return parser.parse_args()


def select_target_users(max_behaviors, min_interest_tags):
    users = db.session.scalars(db.select(User)).all()
    selected = []
    for user in users:
        behavior_count = db.session.scalar(
            db.select(db.func.count())
            .select_from(UserBehavior)
            .filter(
                UserBehavior.user_id == user.id,
                UserBehavior.behavior_type.in_(["browse", "like", "favorite", "comment"]),
            )
        )
        if behavior_count > max_behaviors:
            continue
        if len(user.interest_tags) < min_interest_tags:
            continue
        selected.append(user)
    return selected


def build_relevant_set(user):
    interest_tag_ids = {tag.id for tag in user.interest_tags}
    interest_domain_ids = {tag.domain_id for tag in user.interest_tags}
    relevant_post_ids = set()

    posts = db.session.scalars(db.select(Post)).all()
    for post in posts:
        post_tag_ids = {tag.id for tag in post.tags}
        tag_overlap = bool(post_tag_ids & interest_tag_ids)
        domain_overlap = post.domain_id in interest_domain_ids
        if tag_overlap or domain_overlap:
            relevant_post_ids.add(post.id)

    return relevant_post_ids, interest_tag_ids


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


def hit_rate_at_k(recommended, relevant, k):
    rec_k = set(recommended[:k])
    return 1.0 if rec_k & relevant else 0.0


def interest_tag_recall_at_k(recommended_posts, interest_tag_ids, k):
    if not interest_tag_ids:
        return 0.0

    covered_tag_ids = set()
    for post in recommended_posts[:k]:
        covered_tag_ids.update(tag.id for tag in post.tags if tag.id in interest_tag_ids)
    return len(covered_tag_ids) / len(interest_tag_ids)


def evaluate_config(users, enable_hot, k_values):
    metrics = {
        k: {
            "precision": [],
            "recall": [],
            "hit_rate": [],
            "interest_tag_recall": [],
        }
        for k in k_values
    }

    for idx, user in enumerate(users):
        relevant, interest_tag_ids = build_relevant_set(user)
        if not relevant:
            continue

        try:
            results = recommendation_engine.recommend(
                user.id,
                top_n=max(k_values),
                enable_llm=False,
                enable_hot=enable_hot,
            )
        except Exception:
            continue

        recommended_ids = [item["post_id"] for item in results]
        recommended_posts = [db.session.get(Post, post_id) for post_id in recommended_ids]
        recommended_posts = [post for post in recommended_posts if post is not None]

        for k in k_values:
            metrics[k]["precision"].append(precision_at_k(recommended_ids, relevant, k))
            metrics[k]["recall"].append(recall_at_k(recommended_ids, relevant, k))
            metrics[k]["hit_rate"].append(hit_rate_at_k(recommended_ids, relevant, k))
            metrics[k]["interest_tag_recall"].append(
                interest_tag_recall_at_k(recommended_posts, interest_tag_ids, k)
            )

        if (idx + 1) % 50 == 0:
            print(f"  进度: {idx + 1}/{len(users)}")

    averaged = {}
    for k in k_values:
        sample_size = len(metrics[k]["precision"])
        if sample_size == 0:
            averaged[k] = {
                "precision": 0.0,
                "recall": 0.0,
                "hit_rate": 0.0,
                "interest_tag_recall": 0.0,
                "samples": 0,
            }
            continue

        averaged[k] = {
            "precision": sum(metrics[k]["precision"]) / sample_size,
            "recall": sum(metrics[k]["recall"]) / sample_size,
            "hit_rate": sum(metrics[k]["hit_rate"]) / sample_size,
            "interest_tag_recall": sum(metrics[k]["interest_tag_recall"]) / sample_size,
            "samples": sample_size,
        }
    return averaged


def print_results(all_results, k_values):
    print("\n" + "=" * 108)
    print(f"{'配置':<14}", end="")
    for k in k_values:
        print(f"| P@{k:<3} R@{k:<3} HR@{k:<3} TagRecall@{k:<3}", end="")
    print()
    print("-" * 108)

    for config_name, result in all_results.items():
        print(f"{config_name:<14}", end="")
        for k in k_values:
            metrics = result[k]
            print(
                f"| {metrics['precision']:.4f} {metrics['recall']:.4f} "
                f"{metrics['hit_rate']:.4f} {metrics['interest_tag_recall']:.4f} ",
                end="",
            )
        print()
    print("=" * 108)


def main():
    args = parse_args()
    app = create_app()

    with app.app_context():
        users = select_target_users(args.max_behaviors, args.min_interest_tags)
        if not users:
            print("未找到符合条件的冷启动/低行为用户，可调大 --max-behaviors 再试")
            return

        print("===== 冷启动召回评估 =====")
        print(f"目标用户数: {len(users)}")
        print(f"最多行为数: {args.max_behaviors}")
        print(f"K 值: {args.k}")

        all_results = {}
        for config_name, enable_hot in COMPARE_CONFIGS.items():
            print(f"\n评估 {config_name} (enable_hot={enable_hot})")
            all_results[config_name] = evaluate_config(users, enable_hot, args.k)

        print_results(all_results, args.k)


if __name__ == "__main__":
    main()
