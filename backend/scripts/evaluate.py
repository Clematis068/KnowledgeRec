"""
消融实验评估脚本
评估指标: Precision@K, Recall@K, NDCG@K
消融配置: 单通道 / 双通道组合 / 完整多路融合

用法: cd backend && uv run python -m scripts.evaluate
"""
import sys
import os
import math
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app import create_app, db
from app.models.behavior import UserBehavior
from app.models.user import User
from app.services.recommendation import recommendation_engine


# 消融实验配置
ABLATION_CONFIGS = {
    "CF_only":          {'cf': 1.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.0},
    "Swing_only":       {'cf': 0.0, 'swing': 1.0, 'graph': 0.0, 'semantic': 0.0},
    "Graph_only":       {'cf': 0.0, 'swing': 0.0, 'graph': 1.0, 'semantic': 0.0},
    "Semantic_only":    {'cf': 0.0, 'swing': 0.0, 'graph': 0.0, 'semantic': 1.0},
    "CF+Swing":         {'cf': 0.5, 'swing': 0.5, 'graph': 0.0, 'semantic': 0.0},
    "CF+Graph":         {'cf': 0.5, 'swing': 0.0, 'graph': 0.5, 'semantic': 0.0},
    "CF+Semantic":      {'cf': 0.5, 'swing': 0.0, 'graph': 0.0, 'semantic': 0.5},
    "Swing+Graph":      {'cf': 0.0, 'swing': 0.5, 'graph': 0.5, 'semantic': 0.0},
    "Swing+Semantic":   {'cf': 0.0, 'swing': 0.5, 'graph': 0.0, 'semantic': 0.5},
    "Graph+Semantic":   {'cf': 0.0, 'swing': 0.0, 'graph': 0.5, 'semantic': 0.5},
    "Full_Fusion":      {'cf': 0.28, 'swing': 0.12, 'graph': 0.32, 'semantic': 0.28},
}

K_VALUES = [5, 10, 20]


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
    """Precision@K"""
    rec_k = set(recommended[:k])
    if not rec_k:
        return 0.0
    return len(rec_k & relevant) / k


def recall_at_k(recommended, relevant, k):
    """Recall@K"""
    rec_k = set(recommended[:k])
    if not relevant:
        return 0.0
    return len(rec_k & relevant) / len(relevant)


def ndcg_at_k(recommended, relevant, k):
    """NDCG@K"""
    dcg = 0.0
    for i, item in enumerate(recommended[:k]):
        if item in relevant:
            dcg += 1.0 / math.log2(i + 2)

    # 理想DCG
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

    # 计算平均值
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

        # 输出结果表格
        print("\n" + "=" * 80)
        print(f"{'配置':<20}", end="")
        for k in K_VALUES:
            print(f"| P@{k:<3} R@{k:<3} NDCG@{k:<3}", end="")
        print()
        print("-" * 80)

        for config_name, avg in all_results.items():
            print(f"{config_name:<20}", end="")
            for k in K_VALUES:
                m = avg[k]
                print(f"| {m['precision']:.4f} {m['recall']:.4f} {m['ndcg']:.4f}  ", end="")
            print()

        print("=" * 80)


if __name__ == '__main__':
    main()
