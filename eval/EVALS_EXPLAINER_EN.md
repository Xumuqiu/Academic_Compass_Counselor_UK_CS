# Evals explainer

## What was evaluated

The primary metrics are unsupported concrete claims / all published concrete claims, and correctly detected predefined evidence gaps / relevant reference gaps. The original unsupported-claim target is below 10%. Useful fact opportunity retention, empty output, delivery failures and costs are auxiliary measures. Rules are in [SCORING_RULES.md](SCORING_RULES.md).

The twenty-case main real-model run is `results/paired/20261003T183705Z-8d15689b`. It produced forty documents using OpenRouter `openai/gpt-4.1-mini`. Both arms share fixed interview turns, parsed records and one candidate; one adds claim review. Therefore, it evaluates the incremental guard, not a completely unstructured baseline or dynamic interview effectiveness. Gold references were not supplied to the model.

## Judgements and results

`judgements/final_v1/` contains 1,265 atomic claim judgements, 56 gap judgements, 112 retention judgements and 40 case statuses. Claims are supported, overstated, insufficient or contradicted; the latter three count as unsupported. Published narrative is included even when it is assembled from records. Raw audit records are not automatically treated as published claims. Repeated claims are merged according to the rules.

Judgements refer to the original CV and actually delivered answers, not the guard's verdict or hidden answer bank. `review_provenance.json` discloses single-AI-rater scoring and lack of independent human review. Anonymisation does not establish independent blindness. Citation error rate was not systematically evaluated.

The baseline reached 137/671=20.42% unsupported claims; the guarded arm 103/594=17.34%. Both missed the target. Gap coverage was 23/28=82.14%, retention 56/56=100%, and failures 0/20 in both arms. Coverage and retention often came from preserving limitations and facts already stated, not new professional insight. Narrative accounted for 85 of the guarded arm's 103 errors. The twenty synthetic, previously seen cases do not establish generalisation or statistical significance.

## Files and reproduction

- `run_manifest.json`, `snapshot/`: parameters, protocol, source/data/reference versions.
- `blind_pack.jsonl`, `private/blind_mapping.json`: outputs and case/arm identities. The folder name `private` denotes evaluation mapping, not student secrets, and is necessary for score reproduction.
- `cases/`: delivered documents and raw run records; forty main-run DOCX files.
- `calls.csv`, `calls.jsonl`, `summary.json`: model usage and costs.
- `artifacts_sha256.json`: 152 frozen artifact hashes.
- `scored_metrics.json`, `supplementary_analysis.json`: aggregates and failure breakdown.
- Failed and successful pilots are retained; they are not overwritten by the main run.

From the project root, `python3 -m scripts.verify_saved_results` verifies hashes and recalculates group/per-case summaries without writes or model requests. It reuses saved semantic labels, not independent judgement. `python3 -m eval.paired_eval --dry-run --split dev` checks fixture machinery and makes no model requests; it must not be used as live quality evidence. The old `run_offline`/`run_live` tools cover the earlier challenge set, not this full paired protocol.

## Cost and interpretation

The main run made 176 calls costing USD0.123158; shared upstream USD0.0547116 and guard increment USD0.0684464. The standalone guarded cost was USD0.00615790 per successful case, about 2.25 times the baseline. The experiment shared upstream only once: do not add the baseline cost again to experimental spending. Including connection checks and both pilots, recorded API spending was USD0.1839696. Costs use returned usage.cost, exclude preparation/annotation time and Codex subscription, and do not prove cost effectiveness.

Detailed evidence: [output evaluation](OUTPUT_EVALUATION_REPORT.md), [run and costs](STEP4_RESULTS.md), [cost JSON](results/step4_cost_analysis.json). Saved scores cannot be overwritten by the aggregator; further reviewers need separate judgement versions. New live runs require credentials, incur costs and may generate different outputs.
