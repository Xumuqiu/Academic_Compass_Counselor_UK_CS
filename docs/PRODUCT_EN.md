# Product documentation

## Persona, problem and scope

The primary user is a counsellor advising UK undergraduate Computer Science applicants. CV activity labels often lack evidence about personal contribution, methods, understanding and outcomes. The workbench records these details and organises material for counsellor review. The student supplies answers. The output is a brainstorming brief, not a finished personal statement, admission prediction or academic plan.

## Input and output

Input: a JSON CV with `student.subjects` and `student.experiences`, each including title, role, skills, outputs and an optional experience type. Use [the fictional sample](../data/sample_cv.json). Select one or more local programmes, then supply student answers. Compatibility document inputs exist but are not required for this submission.

Output: a candidate theme, experience cards, six-dimension records, writing angles, narratives, UCAS three-question mapping, evidence sources, outstanding questions and a claim audit where available. The same original result is exported to DOCX. The English/Chinese toggle affects interface copy and standard question templates, not factual statements or model claims.

## Architecture

```text
Selected programmes + JSON CV
             |
             v
Input validation -> multi-experience state + fact IDs/sources
             |
             v
Rule/template question selection <-> student answers
             |                       |
             |             live LLM answer parsing
             v
LLM candidate theme and angles
             |
             v
LLM semantic review + quotation/ownership/number/coverage rules
             |
             v
Optional narrowed wording and second review
             |
             v
Final assembly <--- recorded-fact narratives (currently not fully checked)
             |
             v
Web brief + Word document for counsellor review
```

In demo mode, local templates replace model operations. In live mode, the rented model is `openai/gpt-4.1-mini` via OpenRouter. The state, question selection, quote checks, numeric checks and document exporter are built in code. Programme data is local lookup, not vector RAG. Semantic review uses the same model provider and is not independent truth verification.

## Guard boundary and measured outcomes

The guard checks candidate themes and angles against recorded evidence, requiring complete claim segmentation, exact quotations, right-experience ownership and confirmation status. Unsupported wording can be withheld or narrowed. Final narratives can still publish unconfirmed, corrected or incorrectly parsed facts; all output needs review. Student statements are not independently verified events.

Original target: unsupported-claim rate below 10%. On 20 synthetic paired cases, the baseline reached 20.42% (137/671) and the guarded arm 17.34% (103/594); neither achieved the target. Both reached gap coverage 82.14% (23/28), fact opportunity retention 100% (56/56), and zero delivery failures. Gap coverage had no predefined numerical pass threshold. The two arms share structured parsing and a candidate, so this is an incremental guard comparison. The data and single-rater judgements are AI-authored, not independent held-out validation. See [eval explainer](../eval/EVALS_EXPLAINER_EN.md).

The guarded workflow's per-case API cost was USD0.00615790, about 2.25 times baseline. The main experiment cost USD0.123158; connection checks and pilots bring recorded API spending to USD0.1839696. Human time and Codex costs were not measured.

## Modules

| Module | Responsibility |
| --- | --- |
| `web/`, `counselor/server.py` | Bilingual UI, local session APIs and workflow orchestration |
| `counselor/intake.py`, `cv.py` | Input normalisation and compatibility intake |
| `counselor/workflow.py` | Six dimensions, question selection, fact state and final assembly |
| `counselor/llm.py` | Model requests, parsing, generation and semantic review |
| `counselor/claim_check.py` | Claim coverage, citations, ownership, numeric wording and narrowing rules |
| `counselor/document.py` | Dependency-free DOCX export |
| `counselor/config.py`, `check_llm.py` | Provider configuration and safe connection inspection |
| `counselor/data.py`, `data/` | Local programme data and fictional samples |
| `counselor/domain.py` | Earlier single-experience compatibility path |
| `eval/paired_eval.py`, `score_paired.py` | Frozen paired runs, costs and aggregation of supplied judgements |
| `scripts/`, `tests/` | Credential-free launch, saved-result verification and automated tests |

## Limits

Only local loopback hosting and in-memory sessions are implemented; no login, persistent archive or case-deletion interface exists. Live mode sends material to the provider. The eleven programme entries need verification against their sources. Limited grade rules are not full eligibility assessment. Independent counsellor usefulness, time savings and student outcomes have not been measured.
