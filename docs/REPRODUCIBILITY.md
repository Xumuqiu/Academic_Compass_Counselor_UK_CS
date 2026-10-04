# 运行与复现说明

所有命令在`Academic_Compass_UK_CS_Counselor`内执行。JSON流程、网页、DOCX和评分工具仅需Python标准库，不必安装可选PDF依赖。实际验证环境与结果见[复现检查](reproduction_check.json)。

## 无密钥演示

```bash
python3 --version
COUNSELOR_MODE=demo python3 -m counselor.server
```

打开 http://127.0.0.1:8010/ ，选择项目、使用虚构案例或上传`data/sample_cv.json`，逐轮回答、生成素材包、下载DOCX。可以跳过或提前结束。Ctrl+C停止，重启后会话失效。demo使用模板，不调用模型，不证明live质量。

显式设demo防止开发目录中的`.env.local`启用live。端口占用时用`COUNSELOR_PORT=8011 COUNSELOR_MODE=demo python3 -m counselor.server`。

```bash
COUNSELOR_MODE=demo python3 -m unittest discover -s tests -q
COUNSELOR_MODE=demo python3 -m eval.paired_eval --dry-run --split dev
```

测试检查状态、来源、核查规则、连接配置、API与DOCX。dry-run新增带时间戳的6例夹具run，零模型请求，禁止算作真实质量分数。

## 不花API费核验已保存结果

以下只读脚本检查冻结产物和评分CSV哈希，并用原工具复算组级与逐例汇总，不修改输出或评分：

```bash
COUNSELOR_MODE=demo python3 - <<'PY'
import json
from pathlib import Path
from eval.paired_eval import digest
from eval.score_paired import aggregate, read_csv
run = Path('eval/results/paired/20261003T183705Z-8d15689b')
manifest = json.loads((run/'run_manifest.json').read_text())
assert not manifest['dry_run']
files = json.loads((run/'artifacts_sha256.json').read_text())['files']
for name, expected in files.items():
    assert digest(run/name) == expected, name
saved = json.loads((run/'scored_metrics.json').read_text())
folder = run/'judgements'/'final_v1'
judgements = {n: read_csv(folder/f'{n}.csv') for n in ('claims','gaps','opportunities','cases')}
for name, expected in saved['judgement_file_hashes'].items():
    assert digest(folder/f'{name}.csv') == expected, name
pack = [json.loads(line) for line in (run/'blind_pack.jsonl').read_text().splitlines()]
mapping = json.loads((run/'private'/'blind_mapping.json').read_text())
gold = {cid: json.loads((run/'snapshot'/cid/'stage_gold.json').read_text()) for cid in manifest['case_ids']}
actual = aggregate(pack, mapping, gold, judgements)
assert actual['arms'] == saved['arms']
assert actual['per_case'] == saved['per_case']
print('Frozen artifacts verified:', len(files))
print(json.dumps(actual['arms'], ensure_ascii=False, indent=2))
PY
```

预期152个冻结产物一致；基线137/671、完整103/594；缺口均23/28，保留均56/56。这是数学汇总复算，不是对语义判断的独立复核。旧run的`score_paired`拒绝覆盖首次评分，所以使用以上只读方式。

## 可选：重新调用真实模型（收费）

复制`.env.example`为`.env.local`，在本机填写：

```ini
COUNSELOR_MODE=live
COUNSELOR_PROVIDER=openrouter
COUNSELOR_MODEL=openai/gpt-4.1-mini
OPENROUTER_API_KEY=YOUR_LOCAL_KEY
COUNSELOR_TIMEOUT=30
```

真实密钥不进示例、截图、聊天或提交包。进程环境覆盖`.env.local`覆盖`.env`。供应商必须匹配密钥；修改配置后重启。

```bash
python3 -m counselor.check_llm
python3 -m counselor.check_llm --live
python3 -m eval.paired_eval --live --split dev --budget 10
```

第一条不发请求，第二条验证连接，第三条新跑6例开发预跑。取得成功输出中的新run路径，替换下一条占位值：

```bash
python3 -m eval.paired_eval --live --split evaluation_candidates --pilot-run eval/results/paired/NEW_SUCCESSFUL_DEV_RUN --budget 10
```

候选运行必须匹配成功6例预跑的源码、数据与配置。预算10是美元上限，不表示收费10美元。历史主运行176次请求USD0.123158；新输出、重试与价格可能变化，不保证逐字重现。保留新的run目录，不覆盖历史。

按`eval/SCORING_RULES.md`对新运行实际输出填写claims/gaps/opportunities/cases四份CSV，并记录评分者来源。对尚未评分的新run：

```bash
python3 -m eval.score_paired eval/results/paired/NEW_RUN --judgements PATH_TO_FINAL_CSV_FOLDER --rater '实际评分者身份与方式'
```

旧20例已被查看，重跑不是新的held-out；独立泛化评测需要新案例与外部复核。不要重新生成原数据或重写首次标注来追求好看结果。

## 提交与文件导航

仅提交独立项目目录，保留counselor/web/data/tests/eval/docs、README、requirements和安全的`.env.example`。排除`.env`、`.env.local`、其他密钥、缓存、虚拟环境和.git；不要打包父目录的真实学生材料。保留失败预跑。

- [产品说明](PRODUCT.md)：persona、输入、输出、架构、模块地图、指标与限制。
- [提案核对](statement_alignment.md)：范围变化及V2决策。
- [数据说明](../eval/data_explainer.md)、[评测说明](../eval/evals_explainer.md)。
- [质量结果](../eval/OUTPUT_EVALUATION_REPORT.md)、[调用费用](../eval/STEP4_RESULTS.md)。

干净目录检查不等于跨平台全面测试；浏览器视觉与中文Word字体需人工查看。live数据由外部供应商处理，机构部署所需授权、访问控制及删除政策未完成。
