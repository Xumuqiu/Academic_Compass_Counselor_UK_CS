# Academic Compass — UK Undergraduate CS Brainstorming

**PE6201 End-of-Course Project · Xu Muqiu · Section C · 4 October 2026**

A counsellor-facing research prototype: structured JSON CV → multi-experience interview → reviewable brainstorming brief → Word export. Academic planning is outside this submission's scope.

## Start here: no API key or installation required

Unzip the archive, open a terminal in its `Academic_Compass_UK_CS_Counselor` folder, and run:

```bash
python3 --version
python3 -m scripts.start_demo
```

On Windows, use `py -3` instead of `python3` if needed. Python 3.9.6 on macOS is the verified runtime; other platforms have not been tested. The JSON workflow, local server, Word export and verification tools use only the Python standard library. Do not install optional PDF dependencies for this demo.

Open **http://127.0.0.1:8010/**. Select a programme, use the fictional sample or import `data/sample_cv.json`, answer questions, then generate the brief and download Word. Questions can be skipped and a partial brief can be generated early. The interface defaults to English, with a Chinese/English switch. Student statements, model content and Word output remain in their original language. Stop the server with Ctrl+C. Sessions are in memory and disappear when the server restarts.

The launcher explicitly selects **demo mode: local templates, no model calls**. This demonstrates the workflow, not semantic model quality. The included quality results come from saved real-model runs. If port 8010 is occupied, stop the other service or set `COUNSELOR_PORT` to another port before launching.

## Submission contents

| Requirement | Entry point |
| --- | --- |
| Final report, approximately 1,200 words | [Final report](report/FINAL_REPORT.md), body 1,232 words |
| Persona, input, output, architecture and target/achieved metrics | [Product documentation](docs/PRODUCT_EN.md) |
| Data and a data explainer | [Data explainer](eval/DATA_EXPLAINER_EN.md), `eval/data/` |
| Evals and an eval explainer | [Eval explainer](eval/EVALS_EXPLAINER_EN.md), `eval/` |
| Saved results, annotations and cost records | `eval/results/paired/20261003T183705Z-8d15689b/` |
| Local reproduction evidence | [ZIP verification](docs/code_zip_verification.json) |
| More detailed reproduction instructions | [Reproduction guide](docs/REPRODUCIBILITY.md) (Chinese) |
| Chinese README | [Chinese guide](README.zh-CN.md) |

The **demonstration video is submitted separately**. It is intentionally not included in this code ZIP. `report/DEMO_OUTLINE.md` and `report/DEMO_SAMPLE_ANSWERS.md` are preparation materials, not the submitted video. The latter contains fictional English answers for the built-in sample.

## Reproduce without paid requests

```bash
python3 -m unittest discover -s tests -q
python3 -m scripts.verify_saved_results
python3 -m eval.paired_eval --dry-run --split dev
```

Expected: **47 passing tests**; **152 frozen artifacts** and four annotation CSV hashes verified; saved group and per-case metrics reproduced. The six-case dry-run creates a new timestamped run, uses fixtures and makes zero model requests. It cannot be used to score real model quality. Do not regenerate the dataset or overwrite saved annotations before verification.

`verify_saved_results` is read-only: it recalculates existing labels, not their correctness. Original outputs, data, scoring rules and model-source snapshots are retained, including unsuccessful development attempts. `PACKAGE_MANIFEST.json` lists the archived files and their SHA-256 hashes, excluding the manifest itself.

## Targets, reached metrics and limitations

| Metric | Without claim guard | With claim guard |
| --- | --- | --- |
| Unsupported concrete claims | 137/671 = 20.42% | 103/594 = 17.34% |
| Original target: below 10% | Not achieved | Not achieved |
| Specific evidence-gap coverage | 23/28 = 82.14% | 23/28 = 82.14% |
| Useful fact opportunities retained | 56/56 | 56/56 |
| Delivery failures | 0/20 | 0/20 |
| API cost per successful case, USD | 0.00273558 | 0.00615790 |

The twenty cases are AI-authored synthetic candidates, already seen by the developer. A single AI rater scored them with AI-authored references. There is **no independent held-out or human validation**. Both arms share structured parsing and the generated candidate, so this tests the guard's additional effect, not the original proposal's completely unstructured baseline. Much of coverage and retention comes from preserving student statements. The final narratives are not fully guarded: 85 of the guarded arm's 103 unsupported claims occur there. This prototype requires counsellor review.

The main paired run used 176 requests costing USD **0.123158**. Including connection checks and both development pilots, recorded API spending was USD **0.1839696**. Human time, Codex subscription and account charges are not included.

## Optional live model use (requires your own key and incurs charges)

Only `.env.example` is included; real credentials are excluded. Copy it to `.env.local` and fill in your own OpenRouter key:

```ini
COUNSELOR_MODE=live
COUNSELOR_PROVIDER=openrouter
COUNSELOR_MODEL=openai/gpt-4.1-mini
OPENROUTER_API_KEY=YOUR_LOCAL_KEY
COUNSELOR_TIMEOUT=30
```

Then run:

```bash
python3 -m counselor.check_llm
python3 -m counselor.check_llm --live
python3 -m counselor.server
```

The first command checks configuration only; `--live` makes a small paid request. Use `counselor.server`, not the demo launcher, for live mode. Process settings override `.env.local`, which overrides `.env`. Keys are provider-specific. Do not publish them.

For a new real paired experiment, first run a successful six-case dev pilot, then use its returned directory:

```bash
python3 -m eval.paired_eval --live --split dev --budget 10
python3 -m eval.paired_eval --live --split evaluation_candidates --pilot-run eval/results/paired/NEW_SUCCESSFUL_DEV_RUN --budget 10
```

The second command's placeholder must be replaced. Pilot code, data and model settings must match. Outputs are nondeterministic, costs may change, and a new run requires new output judgements to score quality. Do not overwrite the original run. These previously seen cases do not become new held-out data by rerunning them.

## Module guide and responsible use

[Product documentation](docs/PRODUCT_EN.md) maps the modules and transformation steps. The application binds only to `127.0.0.1`; there is no authentication or persistent student archive. In live mode, relevant profile material and answers are sent to the model provider. Do not assume JSON has been fully de-identified. Submission examples are fictional. Eleven local programme entries remain unverified; limited grade rules do not establish eligibility. Word package structure has been checked; final Chinese typography depends on the viewer's fonts.
