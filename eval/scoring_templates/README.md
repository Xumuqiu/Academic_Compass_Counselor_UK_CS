# 人工评分与运行记录表

这些CSV是空白模板，未包含真实模型结果。以 [评分规则](../SCORING_RULES.md) 为准。按 UTF-8 保存；多条来源可使用 JSON 字符串数组。模板无需发送给系统。

| 文件 | 一行代表什么 | 填写阶段 |
| --- | --- | --- |
| `gold_gaps.csv` | 一个去重后的缺口，包括是否纳入主指标与可见证据 | 看系统输出前审核 |
| `gold_opportunities.csv` | 一个已支持、可用的具体事实机会 | 看系统输出前审核 |
| `claims.csv` | 一个评分者对一条已发布原子论点的判断 | 匿名评分 |
| `gaps.csv` | 一个评分者对一个预定缺口的检测判断 | 匿名评分，所有纳入项都填，包括遗漏 |
| `opportunities.csv` | 一个评分者对一个预定事实机会的保留判断 | 匿名评分，所有纳入项都填 |
| `cases.csv` | 一个匿名素材包的交付、空输出与完整性情况 | 匿名评分 |
| `adjudications.csv` | 一处分歧与最终裁决 | 独立判分后 |
| `calls.csv` | 一个实际模型请求 | 运行日志，禁止包含凭证 |
| `cost_summary.csv` | 一个案例在某组的成本构成 | 调用记录完整后 |
| `human_time.csv` | 一段数据、评分或裁决工作 | 实际工作后 |
| `run_manifest.json` | 一次运行的配置、冻结项和状态 | 运行前准备，运行后补结果位置 |

## 字段规则

- `include_primary`、`include_retention` 和布尔判定使用 `1/0`；尚未审核留空，不默认为1。
- `claims.label` 使用 `supported/overstated/insufficient/contradicted/pending`。`citation_error` 单独填写；`reason` 必填。
- `gaps.label` 使用 `detected/partial/missed/wrong/pending`。`output_locator` 给出明确命中位置，遗漏可空。
- `opportunities.retained` 使用 `1/0`；保留必须有输出位置及实际证据。
- 证据位置示例：`cv.json#/student/experiences/0/role`、`simulated_transcript.json#/turns/1/answer`。正式运行使用实际记录文件名和位置。
- 论点 `claim_id` 在完成拆分对齐后稳定；出现位置可以多个，完全重复内容不重复计数。评分者首次不同拆分保留原行，再在裁决表记录共同单元映射。
- `confirmation_status` 使用 `student_stated/cv_only/conflicted`。跨来源可分开列出，不能把全部经历统一确认。
- 正式评分者仅收到 `blind_id`，组别映射由实验管理员另存，不放进人工评分表。`case_id` 可保留帮助找输入，不能编码实验组。
- `calls.arm` 使用 `shared/prompt_only/full_guardrail`。`shared` 只记录一次实际请求；两组部署成本各计上游，实际账单不能重复累计。
- 成本与币种必须同时填写。未知费用留空并填 `cost_status=unknown`；未发生请求才是0。单位为所填币种，不默认人民币。
- 原始两人判分与裁决分开保存。正式汇总只用已裁决标签，不覆盖原评分行。

新 [对照运行器与汇总工具](../STEP4_RUNBOOK.md) 会按每轮案例预填缺口/机会编号，并由 `eval.score_paired` 汇总完成且已裁决的评分。不要把空白表、离线夹具或作者示例当作人工评测结果。数据作者、评审身份、独立性与冻结时间要据实填写。
