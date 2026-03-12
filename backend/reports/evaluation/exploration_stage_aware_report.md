# 探索机制修正评估报告

- 生成时间：2026-03-12 18:28
- 改动：在“阶段感知滑动窗口打散”基础上保留 epsilon-greedy 探索
  - 探索概率：`epsilon = 0.10`
  - 插入数量：Top-12 以下插入 1 条，其他插入最多 2 条
  - 探索来源：融合排序中 Top-N 之后、Top-`3N` 之前的候选
- 评估用户数：20（行为影响）/ 6（兴趣对齐）
- K 值：[5, 10, 20]
- 评估报告目录：
  - diversity only: `reports/evaluation/diversity_window_stage_aware_after`
  - diversity + exploration: `reports/evaluation/exploration_stage_aware_after`

## 行为影响指标对比（with_hot）

| K | 指标 | 改动前 | 改动后 | 变化 |
| --- | --- | --- | --- | --- |
| 5 | BehaviorNDCG | 0.3791 | 0.3791 | 0.0% |
| 5 | BehaviorAlign | 0.2941 | 0.2941 | 0.0% |
| 5 | BehaviorTagRecall | 0.1774 | 0.1774 | 0.0% |
| 5 | BehaviorDomainRecall | 0.4555 | 0.4555 | 0.0% |
| 10 | BehaviorNDCG | 0.3257 | 0.3257 | 0.0% |
| 10 | BehaviorAlign | 0.2241 | 0.2241 | 0.0% |
| 10 | BehaviorTagRecall | 0.2585 | 0.2585 | 0.0% |
| 10 | BehaviorDomainRecall | 0.6415 | 0.6415 | 0.0% |
| 20 | BehaviorNDCG | 0.3181 | 0.3182 | +0.0% |
| 20 | BehaviorAlign | 0.2102 | 0.2103 | +0.1% |
| 20 | BehaviorTagRecall | 0.4744 | 0.4739 | -0.1% |
| 20 | BehaviorDomainRecall | 0.9418 | 0.9418 | 0.0% |

## 兴趣对齐指标对比（with_hot）

| K | 指标 | 改动前 | 改动后 | 变化 |
| --- | --- | --- | --- | --- |
| 5 | P@K | 0.7600 | 0.7600 | 0.0% |
| 5 | HR@K | 1.0000 | 1.0000 | 0.0% |
| 10 | P@K | 0.5600 | 0.5600 | 0.0% |
| 20 | P@K | 0.4000 | 0.4000 | 0.0% |

## 分析

1. **修正后探索几乎无副作用**：K=5/10 指标完全保持不变，说明在当前数据集上探索插入很克制。
2. **探索主要影响长尾位置**：只有 K=20 出现极小幅波动，符合“少量非头部替换”的设计目标。
3. **当前收益有限但安全**：探索没有明显拉升指标，但也没有继续损伤冷启动表现。
4. **结论**：可以先保留当前探索开关；后续若想放大效果，建议优先改探索池构造，而不是直接提高 `epsilon`。
