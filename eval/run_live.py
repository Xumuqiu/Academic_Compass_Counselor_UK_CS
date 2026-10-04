"""One-pass real-model evaluation on the frozen synthetic challenge set.

Usage is captured from every DashScope-compatible response. Failures stay in
the denominator. This script never prints or stores the API key.
"""

import argparse
import csv
import hashlib
import json
import os
import random
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from time import perf_counter

from counselor import llm
from counselor.config import model_config
from counselor.claim_check import checked_proposals, propose_narrowings
from counselor.document import export_docx
from counselor.workflow import answer_question, make_result, start_case
from eval.cost import usage_quote
from eval.run_offline import ROOT, RESULTS, load_cases, prepare


def _metered_call_log():
    calls = []
    config = model_config(require_key=False)
    original = llm._structured

    def measured(prompt, max_tokens=1800):
        started = perf_counter()
        name = prompt.get("task", "unknown") if isinstance(prompt, dict) else "unknown"
        try:
            result, usage = original(prompt, max_tokens=max_tokens)
        except Exception as exc:
            calls.append({"step": name, "error": type(exc).__name__,
                          "latency_s": round(perf_counter() - started, 3),
                          "usage": None, "cost_rmb": None, "cost": None,
                          "currency": usage_quote(None, config.provider, config.model)["currency"]})
            raise
        quote = usage_quote(usage, config.provider, config.model)
        calls.append({"step": name, "usage": usage,
                      "latency_s": round(perf_counter() - started, 3),
                      "cost_rmb": quote["cost"] if quote["currency"] == "CNY" else None,
                      **quote})
        return result, usage

    llm._structured = measured
    return calls, original


def _review(state, proposal):
    first, _ = llm.review_full_brief_claims(state, proposal)
    narrowed = propose_narrowings(proposal, first)
    second = None
    if narrowed.get("materials") or narrowed.get("thesis_claim"):
        try:
            second, _ = llm.review_full_brief_claims(state, narrowed)
        except RuntimeError:
            pass  # A failed recheck must leave the narrowed text unpublished.
    checked, questions = checked_proposals(state, proposal, first, second)
    return checked, questions, first, second


def run_case(case, mode):
    calls, original = _metered_call_log()
    started = perf_counter()
    config = model_config(require_key=False)
    row = {"case_id": case["id"], "slice": case["slice"],
           "gold_safe_original": case["gold_safe"], "mode": mode,
           "model": config.model, "provider": config.provider,
           "currency": usage_quote(None, config.provider, config.model)["currency"], "error": None}
    try:
        state, fixed_proposal, _ = prepare(case)
        if mode == "full":
            # The baseline receives the same case and answer, but no model.
            row["demo_result"] = make_result(state)
            # Rebuild only for the live branch so answer parsing is exercised.
            cv = state["case"]
            state = start_case(cv, state["programmes"])
            state = answer_question(state, case["answer"], parse=llm.parse_experience_answer)
            proposal, _ = llm.generate_full_brief(state)
        else:
            proposal = fixed_proposal
        checked, questions, first, second = _review(state, proposal)
        result = make_result(state, checked)
        result["open_questions"].extend(questions)
        row.update({
            "proposal": proposal, "first_review": first, "second_review": second,
            "result": result, "candidate_questions": questions,
            "original_claim_published": (any(
                m["angle"] == case["claim"] for m in checked["materials"])
                if mode == "claim" else None),
            "narrowed_claim_published": (any(
                m["angle"] != case["claim"] for m in checked["materials"])
                if mode == "claim" else None),
            "docx_bytes": len(export_docx(result)),
        })
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    finally:
        llm._structured = original
    row["calls"] = calls
    row["latency_s"] = round(perf_counter() - started, 3)
    row["actual_cost_rmb"] = (round(sum(c["cost_rmb"] for c in calls), 8)
                              if all(c["cost_rmb"] is not None for c in calls) else None)
    row["actual_cost"] = (round(sum(c["cost"] for c in calls), 8)
                          if all(c["cost"] is not None for c in calls) else None)
    return row


def write_blind_pack(cases, rows):
    """Hide arm labels for human usefulness ratings; keep mapping separate."""
    by_id = {case["id"]: case for case in cases}
    entries, mapping = [], {}
    for row in rows:
        if row["error"] or "demo_result" not in row:
            continue
        case = by_id[row["case_id"]]
        for arm, result in (("demo", row["demo_result"]), ("live", row["result"])):
            blind_id = hashlib.sha256(
                f"ukcs-eval-20261003:{case['id']}:{arm}".encode()).hexdigest()[:12]
            mapping[blind_id] = {"case_id": case["id"], "arm": arm}
            content = {key: value for key, value in result.items()
                       if key not in ("mode", "claim_audit")}
            entries.append({"blind_id": blind_id, "case_id": case["id"],
                            "input": {"role": case["role"], "answer": case["answer"]},
                            "result": content})
    random.Random(20261003).shuffle(entries)
    (RESULTS / "blind_pack.jsonl").write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in entries), encoding="utf-8")
    (RESULTS / "blind_mapping.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    with (RESULTS / "judgements_template.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["blind_id", "rater", "useful_grounded", "unsupported_claim",
                         "claim_wording_valid", "missing_handled", "document_complete", "notes"])
        for entry in entries:
            writer.writerow([entry["blind_id"], "", "", "", "", "", "", ""])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("claim", "full"), default="claim")
    args = parser.parse_args()
    try:
        config = model_config()
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from None
    pricing = usage_quote(None, config.provider, config.model)
    os.environ["COUNSELOR_MODE"] = "live"
    cases, digest = load_cases()
    rows = [run_case(case, args.mode) for case in cases]
    RESULTS.mkdir(exist_ok=True)
    output = RESULTS / f"live_{args.mode}_outputs.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                      encoding="utf-8")
    if args.mode == "full":
        write_blind_pack(cases, rows)
    completed = [r for r in rows if not r["error"]]
    known_usages = [c["usage"] for r in rows for c in r["calls"]
                    if isinstance(c.get("usage"), dict)]
    input_tokens = [u.get("prompt_tokens", u.get("input_tokens")) for u in known_usages]
    output_tokens = [u.get("completion_tokens", u.get("output_tokens")) for u in known_usages]
    step_costs = defaultdict(float)
    for row in rows:
        for call in row["calls"]:
            if call["cost"] is not None:
                step_costs[call["step"]] += call["cost"]
    summary = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode, "model": config.model, "provider": config.provider,
        "endpoint": config.base_url, "currency": pricing["currency"],
        "price_checked_on": pricing["price_checked_on"], "price_source": pricing["price_source"], "case_sha256": digest,
        "cases": len(rows), "successes": len(completed),
        "safe_original_passed": None, "safe_total": None,
        "unsafe_original_passed": None, "unsafe_total": None,
        "narrowed_published": (sum(r.get("narrowed_claim_published", False) for r in rows)
                               if args.mode == "claim" else None),
        "request_count": sum(len(r["calls"]) for r in rows),
        "input_tokens": (sum(input_tokens) if all(isinstance(n, int) for n in input_tokens)
                         and len(input_tokens) == sum(len(r["calls"]) for r in rows) else None),
        "output_tokens": (sum(output_tokens) if all(isinstance(n, int) for n in output_tokens)
                          and len(output_tokens) == sum(len(r["calls"]) for r in rows) else None),
        "cost_rmb": (round(sum(r["actual_cost_rmb"] for r in rows), 6)
                     if all(r["actual_cost_rmb"] is not None for r in rows) else None),
        "actual_cost": (round(sum(r["actual_cost"] for r in rows), 6)
                        if all(r["actual_cost"] is not None for r in rows) else None),
        "cost_by_step": {step: round(value, 6) for step, value in step_costs.items()},
        "cost_by_step_rmb": ({step: round(value, 6) for step, value in step_costs.items()}
                             if pricing["currency"] == "CNY" else None),
        "mean_latency_s": round(mean(r["latency_s"] for r in rows), 3),
        "median_latency_s": round(median(r["latency_s"] for r in rows), 3),
        "cost_missing_usage_cases": [r["case_id"] for r in rows
                                     if r["actual_cost"] is None],
        "errors": {r["case_id"]: r["error"] for r in rows if r["error"]},
        "warning": "Agent-authored challenge set; full mode still requires blind human ratings."
    }
    if args.mode == "claim":
        safe = [r for r in rows if r["gold_safe_original"]]
        unsafe = [r for r in rows if not r["gold_safe_original"]]
        summary.update({
            "safe_original_passed": sum(r.get("original_claim_published", False) for r in safe),
            "safe_total": len(safe),
            "unsafe_original_passed": sum(r.get("original_claim_published", False) for r in unsafe),
            "unsafe_total": len(unsafe),
        })
    (RESULTS / f"live_{args.mode}_metrics.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
