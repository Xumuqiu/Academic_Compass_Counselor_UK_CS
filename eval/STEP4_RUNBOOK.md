# 第4步：两组对照运行与结果记录

2026-10-04。新运行器已接入26例合成案例与AI作者参考标注。当前数据不是独立held-out；AI作者标注不是独立人工gold。真实质量指标必须来自真实模型输出的逐条评分。

## 1. 已实现的实验

入口是 `eval.paired_eval`，区别于仍使用旧挑战集的 `eval.run_live`。每例读取JSON CV与已生成的实际规则访谈回放，不把整份回答库提前交给模型。固定问题和回答逐轮送入原工作流，真实模式调用原答案解析器；即使解析器填入后续要素，也保留预定问题，确保gold对应的输入真实送达。这是控制guardrail增量的固定访谈实验，不宣称验证了自然动态访谈质量。

两组共享解析状态与一次候选生成。`prompt_only`通过评测专用渲染器直接发布候选主线与角度，不伪造生产系统的guard通过标记；`full_guardrail`运行现有语义核查、引用/归属/确认/数字检查与收窄复核，再用生产渲染器导出。

当前生产guard只核查主线和角度，会舍弃候选自由写作建议等字段。因此本对照两组都舍弃生成的 `guide_note`、`translated_positioning` 与 `sections` 自由文本，使用共同模板；原候选完整内容仍保留供追溯。评分仍检查最终素材包各可用栏目，不只检查角度。不能将结果描述为核查了生成器的所有自由文本。

## 2. 执行顺序

在 `Academic_Compass_UK_CS_Counselor` 项目目录运行。

先在 `.env.local` 配好 `OPENROUTER_API_KEY`、`COUNSELOR_PROVIDER=openrouter`、`COUNSELOR_MODEL=openai/gpt-4.1-mini` 与 `COUNSELOR_MODE=live`。`.env.example`是公开格式示例，不会自动加载，不应存放真实密钥。2026-10-04已确认用户凭证属于OpenRouter，正确路由的最小连接测试通过；此前OpenAI接口401不代表OpenRouter凭证无效。

```sh
python3 -m counselor.check_llm --live
python3 -m eval.paired_eval --dry-run --split dev
python3 -m eval.paired_eval --live --split dev --budget 10
```

预算单位为供应商计价币种：当前OpenRouter为USD。10是默认运行上限，不表示账户余额；两次独立运行各有自己的上限。实际生成前按保守token上界预留费用，价格未知或预留超过上限时不请求。发生请求但usage/费用未知时，停止后续模型调用并保留失败记录，不填0。

真实6例开发预跑应先检查原始输出、失败与费用。全部两组成功交付且数据、规则、代码和模型配置一致后，才可运行20例候选：

```sh
python3 -m eval.paired_eval --live --split evaluation_candidates --pilot-run eval/results/paired/真实开发运行目录 --budget 10
```

运行器会验证预跑，不接受离线夹具或未成功的开发结果。真实首次结果不重试、不覆盖；需要重试时新建运行并记录原因，不能替换首轮失败。现有数据只支持合成挑战结论，不凭运行器冻结就变成独立held-out。

## 3. 每次运行保存什么

每次写入新目录 `eval/results/paired/<UTC时间-随机ID>/`：

| 文件 | 用途 |
| --- | --- |
| `run_manifest.json` | 首次调用前固定样本、模型、参数、数据/gold/规则/提示源码和代码哈希、预算；运行后更新状态 |
| `snapshot/<case>/` | 本轮CV、实际固定访谈、stage gold；无隐藏回答库与凭证 |
| `cases/<case>/run.json` | 实际问答、共享状态、原候选、核查结果、两组产物、失败和调用日志 |
| `cases/<case>/*.docx` | 两组已交付文档；失败组没有伪造的成功文档 |
| `blind_pack.jsonl` | 随机顺序匿名素材、实际输入与交付状态；隐藏组名和内部审计 |
| `private/blind_mapping.json` | 实验管理员保管的组别映射，不交给评分者 |
| `judgements/*.csv` | 已预填案例ID、缺口ID和事实机会ID的待评分表；论点须从输出实际拆分 |
| `calls.jsonl`、`calls.csv` | 逐模型请求的阶段、归组、usage、费用估算与时延；原始prompt供追溯，无gold/密钥 |
| `cost_summary.csv`、`summary.json` | 交付数、失败及费用；此时不含质量成绩 |
| `artifacts_sha256.json` | 原始运行产物哈希，评分前核对；评分表留作可编辑文件 |

离线运行文件明确带 `verification_fixture` 标记，仅验证流程。Word只做程序结构与导出检查，现有环境的中文显示仍应在Word中检查；不将夹具文档当真实学生或模型产物。

## 4. 标注实际输出并汇总

依据 [评分规则](SCORING_RULES.md)，逐个匿名输出填写 `judgements/claims.csv`、`gaps.csv`、`opportunities.csv` 和 `cases.csv`。评分证据取原始CV与当次实际回答，不能把模型解析或review verdict当真值。参考来源指向原数据的路径时，以本轮snapshot中相同问题/回答及gold保存的原文核对。

时间有限可由Codex协助标注，必须注明AI评分且没有独立人工复核。若有两人评分，原判各自保存，讨论后将裁决后的共同单元另存为最终评分目录；不要把两人的重复行一起求和。额外缺口误报与引用错误可另记录；核心自动汇总处理两项主指标、保留、空输出与失败。

```sh
python3 -m eval.score_paired eval/results/paired/真实运行目录 --rater "Codex AI annotation; no independent human review"
```

也可通过 `--judgements 最终裁决目录` 指定新目录。工具检查缺项、重复、待判标签、输出位置与理由，按两组相同gold分母汇总，输出 `scored_metrics.json`。它拒绝离线夹具、被修改的原始产物和覆盖首次评分。没有发布论点时无依据率为null，不算0%；交付失败保留在缺口与机会分母，命中数为0。

汇总给出两组计数与比例、逐例和五类切片、主/辅助经历保留率，供配对分析。最后选择实际误判/失败原例解释误放、误拦与遗漏，不从夹具捏造模型失败。

## 5. 成本分析

分别报告共同解析/生成费用与guard首次/收窄复核增量。独立部署费用：基线=共享上游；完整组=共享上游+guard。实验实际调用支出只算一次上游，不把两组部署费用相加。

记录每尝试案例费用、每成功交付包费用（包括该组失败消耗）、总用量、未知费用请求及重试。OpenRouter实际调用优先记录返回的usage.cost（USD）；预算预留采用2026-10-04官方模型目录的价格快照，不计缓存折扣。缺少usage.cost时费用未知并停止后续调用。OpenAI直连仍按官方价格和返回的缓存用量估算。人工编写/标注/裁决工时另记 `human_time.csv`，未记录的工时不能虚构。

连接检查与其他诊断调用不在本轮案例日志中，应在总项目成本说明中另列。当前离线流程无模型请求，API费用为0；历史401诊断没有usage，其费用状态未知。

## 开发预跑记录（2026-10-04）

首次OpenRouter真实预跑：`20261003T183215Z-3d8049a4`，6例两组均仅1例交付，5例生成结果未满足经历ID完整性；44请求，接口报告USD 0.0204704。未计算质量分数，也未放行候选20例。随后明确每经历一条材料的输出约束，并保存结构失败的原候选与逐调用响应；新版本预跑另存目录，不覆盖首轮。
