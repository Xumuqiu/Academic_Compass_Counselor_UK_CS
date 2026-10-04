"""Frozen synthetic challenge set: quote-only baseline vs claim guard.

The reviewer verdicts here are fixtures. This measures deterministic handling
of correct and incorrect review outputs, not real model judgment quality.
"""

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from counselor.claim_check import checked_proposals
from counselor.data import list_programmes
from counselor.document import export_docx
from counselor.intake import normalize_cv
from counselor.workflow import answer_question, make_result, start_case
from eval.cost import SCENARIOS, scenario_totals

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "offline_cases.json"
RESULTS = ROOT / "results"
FROZEN_SHA256 = "d1d7213fd84ad2a3011550c2e31ace35fd54a45a96240be2f959a612b4e42c49"


def load_cases():
    raw = DATA.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != FROZEN_SHA256:
        raise RuntimeError("case file differs from the frozen evaluation set")
    cases = json.loads(raw)
    if len(cases) != 20 or len({c["id"] for c in cases}) != 20:
        raise RuntimeError("frozen set must contain 20 unique cases")
    return cases, digest


def prepare(case):
    experiences = [{"title": "虚构项目 " + case["id"], "role": case["role"],
                    "skills": ["Python"], "outputs": [], "type": "project"}]
    if any(s.get("fact") == "other_experience" for s in case["segments"]):
        experiences.append({"title": "另一段经历", "role": "制作图形界面",
                            "skills": ["HTML"], "outputs": [], "type": "project"})
    cv = normalize_cv({"student": {"label": "虚构学生", "subjects": [],
                                    "experiences": experiences}})
    state = start_case(cv, list_programmes()[:1])
    state = answer_question(state, case["answer"])
    first = state["records"][0]
    dialog = next((f for f in first["fact_items"] if f["source"] == "dialog:r1"), None)
    cv_fact = next(f for f in first["fact_items"] if f["confirmation"] == "recorded_cv")
    other = state["records"][1]["fact_items"][0] if len(state["records"]) > 1 else None
    facts = {"dialog": dialog, "cv": cv_fact, "other_experience": other}
    segments = []
    for spec in case["segments"]:
        ref = spec.get("fact")
        if ref == "unknown":
            evidence = [{"fact_id": "exp_99:process:0", "quote": "不存在的经历"}]
        elif ref:
            fact = facts[ref]
            evidence = ([{"fact_id": fact["id"], "quote": fact["text"]}]
                        if fact is not None else [])
        else:
            evidence = []
        segments.append({"text": spec["text"], "verdict": spec["verdict"],
                         "evidence": evidence})
    proposal = {"materials": [{"experience_id": "exp_1", "angle": case["claim"],
                               "evidence_quote": case["anchor"]}]}
    review = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                          "claim": case["claim"], "segments": segments}]}
    return state, proposal, review


def run_case(case):
    started = perf_counter()
    state, proposal, review = prepare(case)
    record = state["records"][0]
    quote_only = any(case["anchor"] in value for value in record["values"].values()
                     if isinstance(value, str))
    checked, questions = checked_proposals(state, proposal, review)
    result = make_result(state, checked)
    docx = export_docx(result)
    with ZipFile(BytesIO(docx)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    document_ok = ("论点措辞与事实核查" in xml
                   and "Learning Plan" not in xml and "学业规划" not in xml)
    published = any(m["angle"] == case["claim"] for m in checked["materials"])
    return {
        "case_id": case["id"], "slice": case["slice"],
        "gold_safe_original": case["gold_safe"],
        "quote_only_published_original": quote_only,
        "guard_published_original": published,
        "guard_status": checked["claim_audit"][0]["status"],
        "questions": questions, "document_ok": document_ok,
        "latency_ms": round((perf_counter() - started) * 1000, 3),
    }


def summarize(rows):
    safe = [r for r in rows if r["gold_safe_original"]]
    unsafe = [r for r in rows if not r["gold_safe_original"]]
    def arm(name):
        return {
            "safe_preserved": sum(r[name] for r in safe), "safe_total": len(safe),
            "unsafe_published": sum(r[name] for r in unsafe), "unsafe_total": len(unsafe),
            "accuracy": round(sum(r[name] == r["gold_safe_original"] for r in rows)
                              / len(rows), 3),
        }
    slices = defaultdict(list)
    for row in rows:
        slices[row["slice"]].append(row)
    return {
        "case_count": len(rows),
        "quote_only": arm("quote_only_published_original"),
        "claim_guard": arm("guard_published_original"),
        "status_counts": dict(Counter(r["guard_status"] for r in rows)),
        "document_ok": sum(r["document_ok"] for r in rows),
        "slice_accuracy": {key: round(sum(r["guard_published_original"] == r["gold_safe_original"]
                                           for r in group) / len(group), 3)
                           for key, group in slices.items()},
        "false_accept_ids": [r["case_id"] for r in unsafe if r["guard_published_original"]],
        "false_reject_ids": [r["case_id"] for r in safe if not r["guard_published_original"]],
        "mean_latency_ms": round(sum(r["latency_ms"] for r in rows) / len(rows), 3),
        "actual_model_requests": 0, "actual_model_tokens": 0, "actual_model_cost_rmb": 0.0,
    }


def main():
    cases, digest = load_cases()
    rows = [run_case(case) for case in cases]
    metrics = summarize(rows)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "offline_outputs.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    manifest = {"run_at_utc": datetime.now(timezone.utc).isoformat(),
                "case_sha256": digest, "dataset_origin": "agent-authored synthetic",
                "reviewer": "frozen fixtures, no model calls", "metrics": metrics,
                "cost_scenarios": {name: scenario_totals(calls)
                                   for name, calls in SCENARIOS.items()}}
    (RESULTS / "offline_metrics.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
