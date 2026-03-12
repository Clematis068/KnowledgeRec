"""
用户成长评估脚本：同时看注册兴趣冷启动效果，以及后续交互行为对推荐的影响。

评估分为两部分：
1. 兴趣对齐评估（冷启动/低行为用户）
   - Precision@K / Recall@K / HitRate@K
   - InterestTagRecall@K
   - relevant 定义为：帖子与注册兴趣 tag 或 domain 匹配
2. 行为影响评估（已有一定交互的用户）
   - BehaviorNDCG@K：推荐结果与“交互行为画像”诱导出的加权相关性一致程度
   - BehaviorAlign@K：Top-K 推荐与行为画像的平均匹配强度
   - BehaviorTagRecall@K / BehaviorDomainRecall@K：Top-K 对行为偏好的覆盖率
   - 额外输出不同用户阶段的平均融合权重，观察交互增加后各召回路由的占比变化

用法:
  cd backend && uv run python -m scripts.evaluate_cold_start
  cd backend && uv run python -m scripts.evaluate_cold_start --max-behaviors 10 --behavior-min-count 6 --k 5 10 20
"""
import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.post import Post
from app.models.user import User
from app.services.recommendation import recommendation_engine
from app.services.user_interest_service import BEHAVIOR_PROFILE_WEIGHTS


COMPARE_CONFIGS = {
    "without_hot": False,
    "with_hot": True,
}

POSITIVE_BEHAVIOR_TYPES = ["browse", "like", "favorite", "comment"]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-behaviors", type=int, default=3, help="兴趣对齐评估中，最多保留多少条行为，视作冷启动/低行为用户")
    parser.add_argument("--min-interest-tags", type=int, default=1, help="兴趣对齐评估中，至少拥有多少个注册兴趣标签")
    parser.add_argument("--behavior-min-count", type=int, default=5, help="行为影响评估中，至少需要多少条正向交互行为")
    parser.add_argument("--behavior-history-limit", type=int, default=30, help="行为影响评估中，用最近多少条正向行为构建用户行为画像")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10, 20], help="评估的 K 值")
    parser.add_argument("--report-dir", default="reports/evaluation", help="评估报告输出目录（相对 backend/）")
    parser.add_argument("--disable-exploration", action="store_true", help="评估时关闭探索插入，仅保留主召回 + 打散")
    return parser.parse_args()


def normalize_by_max(scores):
    if not scores:
        return {}
    max_value = max(scores.values())
    if max_value <= 0:
        return {}
    return {
        key: value / max_value
        for key, value in scores.items()
        if value > 0
    }


def behavior_weight(behavior):
    weight = BEHAVIOR_PROFILE_WEIGHTS.get(behavior.behavior_type, 1.0)
    if behavior.behavior_type == "browse":
        weight *= min((behavior.duration or 30) / 60.0, 2.0)
    return weight


def count_positive_behaviors(user_id):
    return db.session.scalar(
        db.select(db.func.count())
        .select_from(UserBehavior)
        .filter(
            UserBehavior.user_id == user_id,
            UserBehavior.behavior_type.in_(POSITIVE_BEHAVIOR_TYPES),
        )
    )


def select_interest_target_users(max_behaviors, min_interest_tags):
    users = db.session.scalars(db.select(User)).all()
    selected = []
    for user in users:
        behavior_count = count_positive_behaviors(user.id)
        if behavior_count > max_behaviors:
            continue
        if len(user.interest_tags) < min_interest_tags:
            continue
        selected.append(user)
    return selected


def select_behavior_target_users(min_behavior_count):
    users = db.session.scalars(db.select(User)).all()
    selected = []
    for user in users:
        behavior_count = count_positive_behaviors(user.id)
        if behavior_count < min_behavior_count:
            continue
        selected.append(user)
    return selected


def build_interest_relevant_set(user, all_posts):
    interest_tag_ids = {tag.id for tag in user.interest_tags}
    interest_domain_ids = {tag.domain_id for tag in user.interest_tags}
    relevant_post_ids = set()

    for post in all_posts:
        post_tag_ids = {tag.id for tag in post.tags}
        tag_overlap = bool(post_tag_ids & interest_tag_ids)
        domain_overlap = post.domain_id in interest_domain_ids
        if tag_overlap or domain_overlap:
            relevant_post_ids.add(post.id)

    return relevant_post_ids, interest_tag_ids


def build_behavior_profile(user_id, all_posts, history_limit):
    stmt = (
        db.select(UserBehavior)
        .filter(
            UserBehavior.user_id == user_id,
            UserBehavior.behavior_type.in_(POSITIVE_BEHAVIOR_TYPES),
        )
        .order_by(UserBehavior.created_at.desc())
        .limit(history_limit)
    )
    behaviors = db.session.scalars(stmt).all()
    if not behaviors:
        return None

    interacted_post_ids = set()
    tag_scores = defaultdict(float)
    domain_scores = defaultdict(float)
    author_scores = defaultdict(float)

    for behavior in behaviors:
        post = db.session.get(Post, behavior.post_id)
        if not post:
            continue

        interacted_post_ids.add(post.id)
        weight = behavior_weight(behavior)

        if post.domain_id:
            domain_scores[post.domain_id] += weight
        if post.author_id:
            author_scores[post.author_id] += weight
        for tag in post.tags:
            tag_scores[tag.id] += weight

    tag_weights = normalize_by_max(tag_scores)
    domain_weights = normalize_by_max(domain_scores)
    author_weights = normalize_by_max(author_scores)

    relevance_scores = {}
    for post in all_posts:
        if post.id in interacted_post_ids:
            continue
        gain = behavior_post_gain(post, tag_weights, domain_weights, author_weights)
        if gain > 0:
            relevance_scores[post.id] = gain

    return {
        "behavior_count": len(behaviors),
        "interacted_post_ids": interacted_post_ids,
        "tag_weights": tag_weights,
        "domain_weights": domain_weights,
        "author_weights": author_weights,
        "relevance_scores": relevance_scores,
    }


def behavior_post_gain(post, tag_weights, domain_weights, author_weights):
    tag_gain = min(sum(tag_weights.get(tag.id, 0.0) for tag in post.tags), 1.0)
    domain_gain = domain_weights.get(post.domain_id, 0.0)
    author_gain = author_weights.get(post.author_id, 0.0)
    return round(tag_gain * 0.5 + domain_gain * 0.3 + author_gain * 0.2, 6)


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


def weighted_ndcg_at_k(recommended_ids, relevance_scores, k):
    rec_k = recommended_ids[:k]
    if not rec_k or not relevance_scores:
        return 0.0

    dcg = 0.0
    for idx, post_id in enumerate(rec_k):
        gain = relevance_scores.get(post_id, 0.0)
        if gain > 0:
            dcg += gain / math.log2(idx + 2)

    ideal_gains = sorted(relevance_scores.values(), reverse=True)[:k]
    idcg = sum(gain / math.log2(idx + 2) for idx, gain in enumerate(ideal_gains))
    return dcg / idcg if idcg > 0 else 0.0


def behavior_alignment_at_k(recommended_ids, relevance_scores, k):
    rec_k = recommended_ids[:k]
    if not rec_k:
        return 0.0
    return sum(relevance_scores.get(post_id, 0.0) for post_id in rec_k) / len(rec_k)


def weighted_tag_recall_at_k(recommended_posts, tag_weights, k):
    if not tag_weights:
        return 0.0

    covered = set()
    for post in recommended_posts[:k]:
        for tag in post.tags:
            if tag.id in tag_weights:
                covered.add(tag.id)

    total_weight = sum(tag_weights.values())
    covered_weight = sum(tag_weights[tag_id] for tag_id in covered)
    return covered_weight / total_weight if total_weight > 0 else 0.0


def weighted_domain_recall_at_k(recommended_posts, domain_weights, k):
    if not domain_weights:
        return 0.0

    covered = {post.domain_id for post in recommended_posts[:k] if post.domain_id in domain_weights}
    total_weight = sum(domain_weights.values())
    covered_weight = sum(domain_weights[domain_id] for domain_id in covered)
    return covered_weight / total_weight if total_weight > 0 else 0.0


def evaluate_interest_alignment(users, all_posts, enable_hot, k_values, enable_exploration):
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
        relevant, interest_tag_ids = build_interest_relevant_set(user, all_posts)
        if not relevant:
            continue

        try:
            results = recommendation_engine.recommend(
                user.id,
                top_n=max(k_values),
                enable_llm=False,
                enable_hot=enable_hot,
                enable_exploration=enable_exploration,
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
            print(f"  [interest] 进度: {idx + 1}/{len(users)}")

    return average_metric_lists(metrics)


def evaluate_behavior_impact(users, all_posts, enable_hot, k_values, history_limit, enable_exploration):
    metrics = {
        k: {
            "behavior_ndcg": [],
            "behavior_align": [],
            "behavior_tag_recall": [],
            "behavior_domain_recall": [],
        }
        for k in k_values
    }
    stage_stats = defaultdict(
        lambda: {
            "users": 0,
            "behavior_count": 0.0,
            "cf": 0.0,
            "graph": 0.0,
            "semantic": 0.0,
            "hot": 0.0,
        }
    )

    for idx, user in enumerate(users):
        profile = build_behavior_profile(user.id, all_posts, history_limit)
        if not profile or not profile["relevance_scores"]:
            continue

        try:
            results, debug_info = recommendation_engine.recommend_with_debug(
                user.id,
                top_n=max(k_values),
                enable_llm=False,
                enable_hot=enable_hot,
                enable_exploration=enable_exploration,
            )
        except Exception:
            continue

        recommended_ids = [item["post_id"] for item in results]
        recommended_posts = [db.session.get(Post, post_id) for post_id in recommended_ids]
        recommended_posts = [post for post in recommended_posts if post is not None]

        for k in k_values:
            metrics[k]["behavior_ndcg"].append(
                weighted_ndcg_at_k(recommended_ids, profile["relevance_scores"], k)
            )
            metrics[k]["behavior_align"].append(
                behavior_alignment_at_k(recommended_ids, profile["relevance_scores"], k)
            )
            metrics[k]["behavior_tag_recall"].append(
                weighted_tag_recall_at_k(recommended_posts, profile["tag_weights"], k)
            )
            metrics[k]["behavior_domain_recall"].append(
                weighted_domain_recall_at_k(recommended_posts, profile["domain_weights"], k)
            )

        stage = debug_info.get("user_stage", "unknown")
        weights_used = debug_info.get("weights_used", {})
        stage_stats[stage]["users"] += 1
        stage_stats[stage]["behavior_count"] += profile["behavior_count"]
        stage_stats[stage]["cf"] += weights_used.get("cf", 0.0)
        stage_stats[stage]["graph"] += weights_used.get("graph", 0.0)
        stage_stats[stage]["semantic"] += weights_used.get("semantic", 0.0)
        stage_stats[stage]["hot"] += weights_used.get("hot", 0.0)

        if (idx + 1) % 50 == 0:
            print(f"  [behavior] 进度: {idx + 1}/{len(users)}")

    return average_metric_lists(metrics), finalize_stage_stats(stage_stats)


def average_metric_lists(metrics):
    averaged = {}
    for k, metric_values in metrics.items():
        sample_size = len(next(iter(metric_values.values()))) if metric_values else 0
        if sample_size == 0:
            averaged[k] = {name: 0.0 for name in metric_values}
            averaged[k]["samples"] = 0
            continue

        averaged[k] = {
            name: sum(values) / sample_size
            for name, values in metric_values.items()
        }
        averaged[k]["samples"] = sample_size
    return averaged


def finalize_stage_stats(stage_stats):
    finalized = {}
    for stage, values in stage_stats.items():
        users = values["users"]
        if users <= 0:
            continue
        finalized[stage] = {
            "users": users,
            "avg_behavior_count": values["behavior_count"] / users,
            "cf": values["cf"] / users,
            "graph": values["graph"] / users,
            "semantic": values["semantic"] / users,
            "hot": values["hot"] / users,
        }
    return finalized


def print_interest_results(all_results, k_values):
    print("\n" + "=" * 116)
    print("兴趣对齐评估（注册兴趣 -> 推荐结果）")
    print(f"{'配置':<14}", end="")
    for k in k_values:
        print(f"| P@{k:<3} R@{k:<3} HR@{k:<3} TagRecall@{k:<3}", end="")
    print()
    print("-" * 116)

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
    print("=" * 116)


def print_behavior_results(all_results, k_values):
    print("\n" + "=" * 132)
    print("行为影响评估（后续交互行为 -> 推荐结果）")
    print(f"{'配置':<14}", end="")
    for k in k_values:
        print(f"| NDCG@{k:<3} Align@{k:<3} BTag@{k:<3} BDom@{k:<3}", end="")
    print()
    print("-" * 132)

    for config_name, result in all_results.items():
        print(f"{config_name:<14}", end="")
        for k in k_values:
            metrics = result[k]
            print(
                f"| {metrics['behavior_ndcg']:.4f} {metrics['behavior_align']:.4f} "
                f"{metrics['behavior_tag_recall']:.4f} {metrics['behavior_domain_recall']:.4f} ",
                end="",
            )
        print()
    print("=" * 132)


def print_stage_summary(stage_stats):
    if not stage_stats:
        return

    order = ["cold", "warm", "active", "unknown"]
    print("\n" + "=" * 84)
    print("行为用户阶段汇总（with_hot 配置）")
    print(f"{'阶段':<10}| {'用户数':<6} {'平均行为数':<10} {'CF':<6} {'Graph':<6} {'Semantic':<9} {'Hot':<6}")
    print("-" * 84)

    for stage in order:
        if stage not in stage_stats:
            continue
        item = stage_stats[stage]
        print(
            f"{stage:<10}| {item['users']:<6} {item['avg_behavior_count']:<10.2f} "
            f"{item['cf']:<6.4f} {item['graph']:<6.4f} {item['semantic']:<9.4f} {item['hot']:<6.4f}"
        )
    print("=" * 84)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(header)
        writer.writerows(rows)


def build_interest_rows(all_results, k_values):
    rows = []
    for config_name, result in all_results.items():
        for k in k_values:
            metrics = result[k]
            rows.append([
                config_name,
                k,
                round(metrics["precision"], 6),
                round(metrics["recall"], 6),
                round(metrics["hit_rate"], 6),
                round(metrics["interest_tag_recall"], 6),
                metrics["samples"],
            ])
    return rows


def build_behavior_rows(all_results, k_values):
    rows = []
    for config_name, result in all_results.items():
        for k in k_values:
            metrics = result[k]
            rows.append([
                config_name,
                k,
                round(metrics["behavior_ndcg"], 6),
                round(metrics["behavior_align"], 6),
                round(metrics["behavior_tag_recall"], 6),
                round(metrics["behavior_domain_recall"], 6),
                metrics["samples"],
            ])
    return rows


def build_stage_rows(stage_stats):
    order = ["cold", "warm", "active", "unknown"]
    rows = []
    for stage in order:
        if stage not in stage_stats:
            continue
        item = stage_stats[stage]
        rows.append([
            stage,
            item["users"],
            round(item["avg_behavior_count"], 4),
            round(item["cf"], 6),
            round(item["graph"], 6),
            round(item["semantic"], 6),
            round(item["hot"], 6),
        ])
    return rows


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


def write_interest_report(path, all_results, k_values, args, user_count):
    rows = build_interest_rows(all_results, k_values)
    headers = ["配置", "K", "P@K", "R@K", "HR@K", "TagRecall@K", "样本数"]
    content = [
        "# 兴趣对齐评估报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 兴趣对齐用户数：{user_count}",
        f"- 低行为阈值：{args.max_behaviors}",
        f"- 最少兴趣标签数：{args.min_interest_tags}",
        f"- K 值：{args.k}",
        "",
        "## 指标表",
        "",
        markdown_table(headers, rows),
        "## 指标说明",
        "",
        "- `P@K`：Top-K 中与注册兴趣匹配的帖子占比。",
        "- `R@K`：注册兴趣相关帖子被 Top-K 命中的比例。",
        "- `HR@K`：Top-K 中是否至少命中 1 条注册兴趣相关帖子。",
        "- `TagRecall@K`：Top-K 覆盖了多少比例的注册兴趣标签。",
        "",
    ]
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(content))


def write_behavior_report(path, all_results, stage_stats, k_values, args, user_count):
    metric_rows = build_behavior_rows(all_results, k_values)
    stage_rows = build_stage_rows(stage_stats)
    metric_headers = ["配置", "K", "BehaviorNDCG@K", "BehaviorAlign@K", "BehaviorTagRecall@K", "BehaviorDomainRecall@K", "样本数"]
    stage_headers = ["阶段", "用户数", "平均行为数", "CF", "Graph", "Semantic", "Hot"]
    content = [
        "# 行为影响评估报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 行为影响用户数：{user_count}",
        f"- 行为最少交互数：{args.behavior_min_count}",
        f"- 行为画像回看条数：{args.behavior_history_limit}",
        f"- K 值：{args.k}",
        "",
        "## 行为影响指标",
        "",
        markdown_table(metric_headers, metric_rows),
        "## 用户阶段权重汇总（with_hot）",
        "",
        markdown_table(stage_headers, stage_rows),
        "## 指标说明",
        "",
        "- `BehaviorNDCG@K`：推荐排序与行为画像相关性的匹配程度，越高越好。",
        "- `BehaviorAlign@K`：Top-K 推荐结果的平均行为匹配强度。",
        "- `BehaviorTagRecall@K`：Top-K 对行为偏好标签的加权覆盖率。",
        "- `BehaviorDomainRecall@K`：Top-K 对行为偏好领域的加权覆盖率。",
        "",
    ]
    with open(path, "w", encoding="utf-8") as fp:
        fp.write("\n".join(content))


def write_reports(report_dir, interest_results, behavior_results, stage_summary, k_values, args, interest_user_count, behavior_user_count):
    ensure_dir(report_dir)

    if interest_results:
        write_csv(
            os.path.join(report_dir, "interest_alignment_metrics.csv"),
            ["config", "k", "precision", "recall", "hit_rate", "interest_tag_recall", "samples"],
            build_interest_rows(interest_results, k_values),
        )
        write_interest_report(
            os.path.join(report_dir, "interest_alignment_report.md"),
            interest_results,
            k_values,
            args,
            interest_user_count,
        )

    if behavior_results:
        write_csv(
            os.path.join(report_dir, "behavior_impact_metrics.csv"),
            ["config", "k", "behavior_ndcg", "behavior_align", "behavior_tag_recall", "behavior_domain_recall", "samples"],
            build_behavior_rows(behavior_results, k_values),
        )
        write_csv(
            os.path.join(report_dir, "stage_weight_summary.csv"),
            ["stage", "users", "avg_behavior_count", "cf", "graph", "semantic", "hot"],
            build_stage_rows(stage_summary),
        )
        write_behavior_report(
            os.path.join(report_dir, "behavior_impact_report.md"),
            behavior_results,
            stage_summary,
            k_values,
            args,
            behavior_user_count,
        )


def main():
    args = parse_args()
    app = create_app()

    with app.app_context():
        all_posts = db.session.scalars(db.select(Post)).all()

        interest_users = select_interest_target_users(args.max_behaviors, args.min_interest_tags)
        behavior_users = select_behavior_target_users(args.behavior_min_count)

        print("===== 用户成长评估 =====")
        print(f"兴趣对齐用户数: {len(interest_users)}")
        print(f"行为影响用户数: {len(behavior_users)}")
        print(f"低行为阈值(max-behaviors): {args.max_behaviors}")
        print(f"最少兴趣标签数: {args.min_interest_tags}")
        print(f"行为评估最少交互数: {args.behavior_min_count}")
        print(f"行为画像回看条数: {args.behavior_history_limit}")
        print(f"K 值: {args.k}")
        print(f"探索插入: {not args.disable_exploration}")

        if not interest_users:
            print("\n未找到符合条件的冷启动/低行为用户，可调大 --max-behaviors 再试")
        if not behavior_users:
            print("\n未找到符合条件的行为评估用户，可调小 --behavior-min-count 再试")

        interest_results = {}
        behavior_results = {}
        stage_summary = {}

        for config_name, enable_hot in COMPARE_CONFIGS.items():
            print(f"\n评估 {config_name} (enable_hot={enable_hot})")

            if interest_users:
                interest_results[config_name] = evaluate_interest_alignment(
                    interest_users, all_posts, enable_hot, args.k, not args.disable_exploration
                )

            if behavior_users:
                behavior_results[config_name], summary = evaluate_behavior_impact(
                    behavior_users,
                    all_posts,
                    enable_hot,
                    args.k,
                    args.behavior_history_limit,
                    not args.disable_exploration,
                )
                if config_name == "with_hot":
                    stage_summary = summary

        if interest_results:
            print_interest_results(interest_results, args.k)
        if behavior_results:
            print_behavior_results(behavior_results, args.k)
            print_stage_summary(stage_summary)

        report_dir = os.path.join(os.getcwd(), args.report_dir)
        write_reports(
            report_dir,
            interest_results,
            behavior_results,
            stage_summary,
            args.k,
            args,
            len(interest_users),
            len(behavior_users),
        )
        print(f"\n报告已写入: {report_dir}")


if __name__ == "__main__":
    main()
