# 探索机制评估报告

- 生成时间：2026-03-12 18:10
- 改动：在滑动窗口打散之后新增 epsilon-greedy 探索插入
  - 探索概率：`epsilon = 0.10`
  - 插入数量：Top-12 以下插入 1 条，其他插入最多 2 条
  - 探索来源：融合排序中 Top-N 之后、Top-`3N` 之前的候选
- 评估用户数：20（行为影响）/ 6（兴趣对齐）
- K 值：[5, 10, 20]
- 评估报告目录：
  - diversity only: `reports/evaluation/diversity_window_after`
  - diversity + exploration: `reports/evaluation/exploration_after`

## 行为影响指标对比（with_hot）

| K | 指标 | 改动前 | 改动后 | 变化 |
| --- | --- | --- | --- | --- |
| 5 | BehaviorNDCG | 0.3791 | 0.3791 | 0.0% |
| 5 | BehaviorAlign | 0.2941 | 0.2941 | 0.0% |
| 5 | BehaviorTagRecall | 0.1774 | 0.1774 | 0.0% |
| 5 | BehaviorDomainRecall | 0.4555 | 0.4555 | 0.0% |
| 10 | BehaviorNDCG | 0.3224 | 0.3257 | +1.0% |
| 10 | BehaviorAlign | 0.2201 | 0.2241 | +1.8% |
| 10 | BehaviorTagRecall | 0.2515 | 0.2585 | +2.8% |
| 10 | BehaviorDomainRecall | 0.6250 | 0.6415 | +2.6% |
| 20 | BehaviorNDCG | 0.3179 | 0.3182 | +0.1% |
| 20 | BehaviorAlign | 0.2101 | 0.2103 | +0.1% |
| 20 | BehaviorTagRecall | 0.4688 | 0.4683 | -0.1% |
| 20 | BehaviorDomainRecall | 0.9418 | 0.9418 | 0.0% |

## 兴趣对齐指标对比（with_hot）

| K | 指标 | 改动前 | 改动后 | 变化 |
| --- | --- | --- | --- | --- |
| 5 | P@K | 0.7200 | 0.7200 | 0.0% |
| 5 | HR@K | 1.0000 | 1.0000 | 0.0% |
| 10 | P@K | 0.3600 | 0.3600 | 0.0% |
| 20 | P@K | 0.2100 | 0.2100 | 0.0% |

## 分析

1. **探索影响温和**：在 `epsilon = 0.10` 的设置下，K=5 完全不受影响，说明探索插入没有破坏头部结果。
2. **K=10 有小幅正收益**：BehaviorNDCG、Align、TagRecall、DomainRecall 均有提升，说明从次优候选中引入少量探索帖是有效的。
3. **冷启动指标保持不变**：当前探索池来源仍局限于较高分候选，因此没有进一步拉低兴趣对齐表现。
4. **结论**：探索机制可以先保留当前轻量版本，后续再根据线上反馈决定是否按用户阶段动态调整 `epsilon`。
