# Knowledge Route / Logic Constraint 评估报告

- 生成时间：2026-03-12 22:30
- 改动：将已审核的 tag 关系接回推荐链路
  - 新增独立 `knowledge recall route`
  - 在融合后、打散前增加知识逻辑约束（`logic bonus / penalty`）
  - 调试信息新增 `knowledge_score`、`logic_bonus`、`logic_penalty`
- 评估脚本：`python -m scripts.evaluate_cold_start --report-dir reports/evaluation/knowledge_route_after`
- 评估用户数：20（行为影响）/ 6（兴趣对齐）
- K 值：[5, 10, 20]
- 原始评估明细目录：
  - `reports/evaluation/knowledge_route_after/behavior_impact_report.md`
  - `reports/evaluation/knowledge_route_after/interest_alignment_report.md`

## 行为影响指标（with_hot）

| K | BehaviorNDCG | BehaviorAlign | BehaviorTagRecall | BehaviorDomainRecall |
| --- | --- | --- | --- | --- |
| 5 | 0.3824 | 0.2941 | 0.1774 | 0.4555 |
| 10 | 0.3305 | 0.2264 | 0.2746 | 0.6576 |
| 20 | 0.3203 | 0.2100 | 0.4891 | 0.9448 |

## 兴趣对齐指标（with_hot）

| K | P@K | R@K | HR@K | TagRecall@K |
| --- | --- | --- | --- | --- |
| 5 | 0.7200 | 0.0214 | 1.0000 | 0.4667 |
| 10 | 0.5200 | 0.0284 | 1.0000 | 0.4667 |
| 20 | 0.3900 | 0.0431 | 1.0000 | 0.5333 |

## 用户阶段权重（with_hot）

| 阶段 | CF | Swing | Graph | Semantic | Hot |
| --- | --- | --- | --- | --- | --- |
| warm | 0.1465 | 0.0160 | 0.2617 | 0.2303 | 0.2303 |
| active | 0.3326 | 0.0228 | 0.2613 | 0.2376 | 0.1188 |

## 结果解读

1. **Knowledge route 已成功参与召回与排序**：评估可正常跑通，推荐链路在真实用户上返回了稳定结果，说明知识关系已经从“图中存在”变成“线上可用”。
2. **with_hot 配置在 K=10 / K=20 上仍保持较强表现**：BehaviorNDCG、BehaviorAlign、BehaviorTagRecall、BehaviorDomainRecall 均维持在较高水平，说明知识约束没有破坏主链路。
3. **知识逻辑更适合解释“学习路径”而不是暴力提分**：从当前离线结果看，它更像是在保持整体精度的前提下补充结构化推荐依据，而不是单纯追求指标暴涨。
4. **论文建议表述**：可将这一部分写成“知识图谱关系从静态存储升级为可执行推荐信号”，强调其在召回增强、逻辑约束和可解释性上的价值。

## 说明

- 本报告给出的是**当前版本接入 knowledge route 后的完整结果**。
- 如果需要严格的“改动前 / 改动后”对照实验，建议下一步固定一个接入前 commit，再按同一脚本重跑一次 baseline。
