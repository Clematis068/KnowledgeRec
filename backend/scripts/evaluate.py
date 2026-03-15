"""
消融实验评估脚本
评估指标: Precision@K, Recall@K, NDCG@K
消融配置: 单通道 / 双通道组合 / 三路组合 / 完整六路融合

用法: cd backend && uv run python -m scripts.evaluate
"""
import csv
import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.user import User
from app.services.recommendation import recommendation_engine


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
}

K_VALUES = [5, 10, 20]
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports", "evaluation")


def split_train_test(test_ratio=0.2):
    """按时间划分训练/测试集：最近20%行为作为测试集"""
    print("划分训练/测试集...")
    users = db.session.scalars(db.select(User)).all()
    test_set = {}  # {user_id: set(post_ids)}

    for user in users:
        stmt = (db.select(UserBehavior)
                .filter_by(user_id=user.id)
                .filter(UserBehavior.behavior_type.in_(['like', 'favorite']))
                .order_by(UserBehavior.created_at))
        behaviors = db.session.scalars(stmt).all()
        if len(behaviors) < 5:
            continue

        split_idx = int(len(behaviors) * (1 - test_ratio))
        test_behaviors = behaviors[split_idx:]
        test_set[user.id] = set(b.post_id for b in test_behaviors)

    print(f"  测试用户数: {len(test_set)}")
    return test_set


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


def evaluate_config(config_name, weights, test_set, k_values):
    """评估单个配置"""
    metrics = {k: {'precision': [], 'recall': [], 'ndcg': []} for k in k_values}

    user_ids = list(test_set.keys())
    for i, user_id in enumerate(user_ids):
        relevant = test_set[user_id]

        try:
            results = recommendation_engine.recommend(
                user_id, top_n=max(k_values), enable_llm=False, weights=weights
            )
            recommended = [r['post_id'] for r in results]
        except Exception:
            continue

        for k in k_values:
            metrics[k]['precision'].append(precision_at_k(recommended, relevant, k))
            metrics[k]['recall'].append(recall_at_k(recommended, relevant, k))
            metrics[k]['ndcg'].append(ndcg_at_k(recommended, relevant, k))

        if (i + 1) % 50 == 0:
            print(f"  [{config_name}] 进度: {i + 1}/{len(user_ids)}")

    avg_metrics = {}
    for k in k_values:
        n = len(metrics[k]['precision'])
        if n == 0:
            avg_metrics[k] = {'precision': 0, 'recall': 0, 'ndcg': 0}
        else:
            avg_metrics[k] = {
                'precision': sum(metrics[k]['precision']) / n,
                'recall': sum(metrics[k]['recall']) / n,
                'ndcg': sum(metrics[k]['ndcg']) / n,
            }

    return avg_metrics


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
            ])
    return rows


def write_reports(all_results, k_values, test_user_count):
    os.makedirs(REPORT_DIR, exist_ok=True)

    rows = build_ablation_rows(all_results, k_values)
    csv_header = ["config", "k", "precision", "recall", "ndcg"]

    # CSV
    write_csv(os.path.join(REPORT_DIR, "ablation_metrics.csv"), csv_header, rows)

    # Markdown 报告
    md_headers = ["配置", "K", "P@K", "R@K", "NDCG@K"]
    content = [
        "# 消融实验评估报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 测试用户数：{test_user_count}",
        f"- K 值：{k_values}",
        f"- 消融配置数：{len(all_results)}",
        "",
        "## 指标表",
        "",
        markdown_table(md_headers, rows),
        "## 配置说明",
        "",
        "- 单路：仅启用 1 个召回通道，其余权重为 0",
        "- 双路：两个通道等权 0.5",
        "- 三路：三个通道近似等权",
        "- Full_Fusion：六路完整融合（与 active 阶段权重一致）",
        "",
        "## 指标说明",
        "",
        "- `P@K`：Top-K 推荐中与测试集匹配的比例（精确率）",
        "- `R@K`：测试集中被 Top-K 命中的比例（召回率）",
        "- `NDCG@K`：考虑排序位置的归一化折扣累计增益",
        "",
    ]
    with open(os.path.join(REPORT_DIR, "ablation_report.md"), "w", encoding="utf-8") as fp:
        fp.write("\n".join(content))


def print_results(all_results, k_values):
    print("\n" + "=" * 80)
    print(f"{'配置':<20}", end="")
    for k in k_values:
        print(f"| P@{k:<3} R@{k:<3} NDCG@{k:<3}", end="")
    print()
    print("-" * 80)

    for config_name, avg in all_results.items():
        print(f"{config_name:<20}", end="")
        for k in k_values:
            m = avg[k]
            print(f"| {m['precision']:.4f} {m['recall']:.4f} {m['ndcg']:.4f}  ", end="")
        print()

    print("=" * 80)


def main():
    app = create_app()
    with app.app_context():
        test_set = split_train_test()
        if not test_set:
            print("测试集为空，请先生成数据并运行预计算")
            return

        print(f"\n===== 消融实验评估 =====")
        print(f"测试用户: {len(test_set)}")
        print(f"K 值: {K_VALUES}")
        print()

        all_results = {}

        for config_name, weights in ABLATION_CONFIGS.items():
            print(f"评估: {config_name} (权重: {weights})")
            avg = evaluate_config(config_name, weights, test_set, K_VALUES)
            all_results[config_name] = avg

        print_results(all_results, K_VALUES)
        write_reports(all_results, K_VALUES, len(test_set))
        print(f"\n报告已写入: {REPORT_DIR}")


if __name__ == '__main__':
    main()
