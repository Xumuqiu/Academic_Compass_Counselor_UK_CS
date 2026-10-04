# 评测文件说明

当前结果入口：[真实输出评测报告](OUTPUT_EVALUATION_REPORT.md)。数据来源另见[data_explainer.md](data_explainer.md)。

## 三种证据不要混用

1. `run_offline.py`与`offline_cases.json`：20个旧开发挑战，review输出是模拟夹具；用于程序行为检查，不是模型质量。
2. `paired_eval --dry-run`：26个JSON CV中的开发数据跑协议、快照与文档导出；无模型调用，禁止计算真实质量分数。
3. `paired_eval --live`：OpenRouter真实调用，20例主运行`results/paired/20261003T183705Z-8d15689b`。两组共享固定访谈回答与解析/候选，完整组加guard。没有测动态访谈效果，也没有完全无schema的原提案基线。

## 评分单位与文件

规则：[SCORING_RULES.md](SCORING_RULES.md)。将已发布学生事实拆为原子论点，以原CV与当轮实际送达回答判断supported/overstated/insufficient/contradicted，后三者计无依据。不能用reviewer判定、隐藏回答库或解析fact当真值。素材总结是可用输出，也计入，不限guard覆盖字段。

主运行中的`judgements/final_v1/claims.csv`包含1265条原子判断；`gaps.csv`56条、`opportunities.csv`112条、`cases.csv`40条。`review_provenance.json`声明同一AI作者评分及边界限制。参考标签是AI-authored，不是独立人工gold；匿名ID也不能保证独立盲评。

`scored_metrics.json`保存按组和按案例的错误率、覆盖、保留、失败、评分文件哈希及费用。`supplementary_analysis.json`拆分叙述与生成角度错误。`run_manifest.json`记录供应商、模型、案例、快照、协议；`artifacts_sha256.json`固定原始产物；`snapshot/`保存当时源码/输入/标签；`calls.csv`及`calls.jsonl`保存调用与费用；`cases/`保存原始输出和40份DOCX。运行器没有将gold输入模型。

## 结果与解释

基线20.42%对完整17.34%，均未达低于10%目标；缺口覆盖均82.14%，事实机会保留均100%。这些高分常来自保留学生已说出的限制和事实，不是顾问质量充分证明。主运行USD0.123158，全部已记录连接与预跑共USD0.1839696；API费不包括人工时间和Codex费用。

保留首次失败预跑与成功预跑，不择优删除记录。20个候选已被开发作者查看，无独立held-out；未做独立人工复核、引用错误率系统评分或显著性判断。原提案9/13与0/13只作早期历史样例，不代替当前20例结果。

## 如何复现

[复现说明](../docs/REPRODUCIBILITY.md)区分无付费流程、只读汇总核验与新的付费模型运行。现有首次汇总禁止覆盖；如另有评分者重新判定，应另存版本和原因。可以复算CSV的数学汇总，但这不等于独立复核CSV里的语义判断。新模型调用输出可能不同，应保留新run目录，不覆盖此版本。
