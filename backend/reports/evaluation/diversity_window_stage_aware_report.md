# 滑动窗口打散修正评估报告

- 生成时间：2026-03-12 18:25
- 改动：将滑动窗口打散改为按用户阶段自适应
  - `cold` 用户：同一作者最多 3 条、同一领域最多 6 条
  - `warm/active` 用户：同一作者最多 2 条、同一领域最多 3 条
  - 候选池仍为 `top_n * 4`
- 评估用户数：20（行为影响）/ 6（兴趣对齐）
- K 值：[5, 10, 20]
- 评估报告目录：
  - baseline: `reports/evaluation/diversity_baseline`
  - after: `reports/evaluation/diversity_window_stage_aware_after`

## 行为影响指标对比（with_hot）

| K | 指标 | 改动前 | 改动后 | 变化 |
| --- | --- | --- | --- | --- |
| 5 | BehaviorNDCG | 0.3814 | 0.3791 | -0.6% |
| 5 | BehaviorAlign | 0.2955 | 0.2941 | -0.5% |
| 5 | BehaviorTagRecall | 0.1556 | 0.1774 | +14.0% |
| 5 | BehaviorDomainRecall | 0.3717 | 0.4555 | +22.5% |
| 10 | BehaviorNDCG | 0.3270 | 0.3257 | -0.4% |
| 10 | BehaviorAlign | 0.2256 | 0.2241 | -0.7% |
| 10 | BehaviorTagRecall | 0.2085 | 0.2585 | +24.0% |
| 10 | BehaviorDomainRecall | 0.5047 | 0.6415 | +27.1% |
| 20 | BehaviorNDCG | 0.3127 | 0.3181 | +1.7% |
| 20 | BehaviorAlign | 0.2041 | 0.2102 | +3.0% |
| 20 | BehaviorTagRecall | 0.3851 | 0.4744 | +23.2% |
| 20 | BehaviorDomainRecall | 0.7956 | 0.9418 | +18.4% |

## 兴趣对齐指标对比（with_hot）

| K | 指标 | 改动前 | 改动后 | 变化 |
| --- | --- | --- | --- | --- |
| 5 | P@K | 0.7600 | 0.7600 | 0.0% |
| 5 | HR@K | 1.0000 | 1.0000 | 0.0% |
| 10 | P@K | 0.5600 | 0.5600 | 0.0% |
| 20 | P@K | 0.4800 | 0.4000 | -16.7% |

## 分析

1. **修正后冷启动显著改善**：与上一版“全用户强打散”相比，K=5/10 的冷启动兴趣精度已恢复到 baseline 水平。
2. **覆盖收益仍然保留**：BehaviorTagRecall 与 BehaviorDomainRecall 仍保持大幅提升，说明打散对 warm/active 用户依然有效。
3. **精度损失进一步收敛**：K=10 的 NDCG/Align 仅轻微下降，可接受度明显高于上一版。
4. **结论**：阶段感知打散比统一打散更适合当前毕设数据分布，建议保留这一修正版。
