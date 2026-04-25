"""精度-多样性散点图：在 NDCG@10 × Entropy@10 平面上对比消融配置。

Baseline 用方块、单路用圆、组合路用三角、GBDT 用五角星高亮。
"""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 支持中文
matplotlib.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti TC", "Arial Unicode MS", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False

CSV = Path(__file__).parent.parent / "reports/evaluation_yelp/ablation_metrics.csv"
OUT = Path(__file__).parent.parent / "reports/evaluation_yelp/accuracy_diversity_scatter.png"

K = 10
BASELINES = {"[B] Random", "[B] Popular", "[B] UserCF"}
SINGLE = {"CF_only", "Swing_only", "Graph_only", "Semantic_only", "Knowledge_only", "Hot_only"}
COMBO = {"CF+Swing", "CF+Graph", "CF+Semantic", "Graph+Semantic",
         "CF+Graph+Sem", "CF+Swing+Graph", "Full_Fusion"}
HIGHLIGHT = {"GBDT_Ranking"}


def _category(config):
    if config in HIGHLIGHT:
        return "GBDT", "#d62728", "*", 380
    if config in BASELINES:
        return "Baseline", "#7f7f7f", "s", 110
    if config in SINGLE:
        return "单路召回", "#1f77b4", "o", 120
    if config in COMBO:
        return "多路融合", "#2ca02c", "^", 130
    return "其它", "#888", ".", 60


def load_rows():
    rows = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if int(row["k"]) != K:
                continue
            rows.append({
                "config": row["config"],
                "ndcg": float(row["ndcg"]),
                "entropy": float(row["entropy"]),
                "coverage": float(row["coverage"]),
                "ils": float(row["ils"]),
            })
    return rows


def plot(rows):
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # ── 子图 1：NDCG@10 × Entropy@10 ──
    ax = axes[0]
    legend_seen = set()
    for r in rows:
        label, color, marker, size = _category(r["config"])
        legend_label = label if label not in legend_seen else None
        legend_seen.add(label)
        ax.scatter(r["ndcg"], r["entropy"], c=color, marker=marker, s=size,
                   edgecolor="black", linewidth=0.6, alpha=0.85, label=legend_label,
                   zorder=3 if label == "GBDT" else 2)
        ax.annotate(r["config"], (r["ndcg"], r["entropy"]),
                    xytext=(5, 4), textcoords="offset points", fontsize=8)

    ax.set_xlabel("NDCG@10 (精度, 越高越好)")
    ax.set_ylabel("Entropy@10 (多样性, 越高越好)")
    ax.set_title("精度 — 多样性 (领域熵) 权衡")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend(loc="lower right", fontsize=9)

    # 帕累托提示箭头
    gbdt = next(r for r in rows if r["config"] == "GBDT_Ranking")
    ax.annotate("帕累托前沿最优",
                xy=(gbdt["ndcg"], gbdt["entropy"]),
                xytext=(gbdt["ndcg"] - 0.045, gbdt["entropy"] + 0.25),
                fontsize=10, color="#d62728",
                arrowprops=dict(arrowstyle="->", color="#d62728", lw=1.2))

    # ── 子图 2：NDCG@10 × (1-ILS)@10 ──
    ax2 = axes[1]
    legend_seen = set()
    for r in rows:
        label, color, marker, size = _category(r["config"])
        legend_label = label if label not in legend_seen else None
        legend_seen.add(label)
        diversity = 1.0 - r["ils"]
        ax2.scatter(r["ndcg"], diversity, c=color, marker=marker, s=size,
                    edgecolor="black", linewidth=0.6, alpha=0.85, label=legend_label,
                    zorder=3 if label == "GBDT" else 2)
        ax2.annotate(r["config"], (r["ndcg"], diversity),
                     xytext=(5, 4), textcoords="offset points", fontsize=8)

    ax2.set_xlabel("NDCG@10 (精度, 越高越好)")
    ax2.set_ylabel("1 − ILS@10 (列表内多样性, 越高越好)")
    ax2.set_title("精度 — 多样性 (列表内) 权衡")
    ax2.grid(True, linestyle="--", alpha=0.4)
    ax2.legend(loc="lower right", fontsize=9)

    fig.suptitle("Yelp 数据集 消融实验：精度 vs 多样性 (K=10)", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    print(f"saved -> {OUT}")


if __name__ == "__main__":
    plot(load_rows())
