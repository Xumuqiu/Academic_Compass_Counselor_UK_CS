"""Claim-level guard: every part of a proposed sentence needs a sourced fact.

The reviewer supplies semantic judgments. Code checks coverage, exact quotations,
fact ownership, confirmation state, and measurable wording before publication.
"""

import re

VERDICTS = {"supported", "overstated", "insufficient", "contradicted"}


def _candidates(proposal):
    materials = proposal.get("materials", []) if isinstance(proposal, dict) else []
    if not isinstance(materials, list):
        materials = []
    for item in materials:
        if (isinstance(item, dict) and isinstance(item.get("angle"), str)
                and isinstance(item.get("experience_id"), str)):
            yield "angle", item.get("experience_id"), item["angle"], item.get("evidence_quote")
    if isinstance(proposal, dict) and isinstance(proposal.get("thesis_claim"), str):
        yield "thesis", None, proposal["thesis_claim"], proposal.get("thesis_evidence_quote")


def propose_narrowings(proposal, review):
    """Collect reviewer suggestions for a *new* independent review call."""
    out = {"materials": []}
    if not isinstance(review, dict) or not isinstance(review.get("claims"), list):
        return out
    known = {(kind, exp_id, claim): quote
             for kind, exp_id, claim, quote in _candidates(proposal)}
    for item in review["claims"]:
        if not isinstance(item, dict):
            continue
        kind, exp_id, claim = item.get("kind"), item.get("experience_id"), item.get("claim")
        proposed = item.get("suggested_wording")
        if (not isinstance(kind, str) or not isinstance(claim, str)
                or (exp_id is not None and not isinstance(exp_id, str))
                or not isinstance(proposed, str) or not proposed.strip() or len(proposed) > 250
                or proposed == claim or (kind, exp_id, claim) not in known):
            continue
        if kind == "angle":
            out["materials"].append({"experience_id": exp_id, "angle": proposed,
                                     "evidence_quote": known[(kind, exp_id, claim)]})
        elif kind == "thesis":
            out["thesis_claim"] = proposed
            out["thesis_evidence_quote"] = known[(kind, exp_id, claim)]
    return out


def _decision(review, kind, exp_id, claim):
    if not isinstance(review, dict) or not isinstance(review.get("claims"), list):
        return None
    matched = [item for item in review["claims"]
               if isinstance(item, dict) and item.get("kind") == kind
               and item.get("experience_id") == exp_id and item.get("claim") == claim]
    return matched[0] if len(matched) == 1 else None


def _assess(state, review, kind, exp_id, claim, anchor_quote):
    """Return an auditable assessment; malformed or incomplete review fails closed."""
    entry = {"kind": kind, "experience_id": exp_id, "claim": claim,
             "status": "insufficient", "segments": []}
    if not isinstance(claim, str) or not claim.strip():
        return entry
    facts = {fact["id"]: fact for record in state["records"]
             if kind == "thesis" or record["experience_id"] == exp_id
             for fact in record["fact_items"]}
    if kind == "angle" and exp_id not in {r["experience_id"] for r in state["records"]}:
        return entry
    if (not isinstance(anchor_quote, str) or not anchor_quote.strip()
            or not any(anchor_quote in fact["text"] for fact in facts.values())):
        entry["status"] = "invalid_reference"
        return entry
    decision = _decision(review, kind, exp_id, claim)
    segments = decision.get("segments") if decision else None
    if not isinstance(segments, list) or not segments or len(segments) > 12:
        entry["status"] = "review_missing"
        return entry
    if any(not isinstance(s, dict) or not isinstance(s.get("text"), str) or not s["text"]
           for s in segments) or "".join(s["text"] for s in segments) != claim:
        entry["status"] = "incomplete_segmentation"
        return entry
    statuses = []
    for segment in segments:
        verdict = segment.get("verdict")
        status = verdict if isinstance(verdict, str) and verdict in VERDICTS else "review_missing"
        anchors = []
        refs = segment.get("evidence", [])
        if status == "supported":
            if not isinstance(refs, list) or not refs:
                status = "invalid_reference"
            else:
                for ref in refs:
                    if not isinstance(ref, dict):
                        status = "invalid_reference"
                        break
                    fact_id = ref.get("fact_id")
                    fact = facts.get(fact_id) if isinstance(fact_id, str) else None
                    quote = ref.get("quote")
                    if (fact is None or not isinstance(quote, str) or not quote.strip()
                            or quote not in fact["text"]):
                        status = "invalid_reference"
                        break
                    anchors.append({"fact_id": fact["id"], "quote": quote,
                                    "source": fact["source"],
                                    "confirmation": fact["confirmation"]})
                if status == "supported" and any(
                        a["confirmation"] != "student_stated" for a in anchors):
                    status = "needs_confirmation"
                if status == "supported":
                    cited_text = " ".join(a["quote"] for a in anchors)
                    numbers = re.findall(r"\d+(?:\.\d+)?%?", segment["text"])
                    if any(number not in cited_text for number in numbers):
                        status = "unsupported_measurement"
        entry["segments"].append({
            "text": segment["text"], "status": status,
            "evidence": anchors,
            "reason": str(segment.get("reason") or "")[:250],
        })
        statuses.append(status)
    entry["status"] = "supported" if all(x == "supported" for x in statuses) else next(
        (x for x in statuses if x != "supported"), "insufficient")
    if entry["status"] == "supported" and not any(
            anchor_quote in facts[anchor["fact_id"]]["text"]
            for part in entry["segments"] for anchor in part["evidence"]):
        entry["status"] = "invalid_reference"
    return entry


def checked_proposals(state, proposal, review, rewrite_review=None):
    """Publish only fully supported original or independently rechecked wording."""
    if not isinstance(proposal, dict):
        return None, []
    accepted = {"materials": [], "claim_audit": [], "_claim_guard_passed": True}
    questions = []
    rewrite_proposal = propose_narrowings(proposal, review)
    rewrites = {(kind, exp_id): (claim, quote)
                for kind, exp_id, claim, quote in _candidates(rewrite_proposal)}
    titles = {r["experience_id"]: r["title"] for r in state["records"]}
    for kind, exp_id, claim, quote in _candidates(proposal):
        original = _assess(state, review, kind, exp_id, claim, quote)
        original["original_status"] = original["status"]
        chosen = original
        if original["status"] != "supported" and (kind, exp_id) in rewrites:
            revised, revised_quote = rewrites[(kind, exp_id)]
            rechecked = _assess(state, rewrite_review, kind, exp_id, revised, revised_quote)
            if rechecked["status"] == "supported":
                chosen = rechecked
                original["status"] = "narrowed_supported"
        original["suggested_wording"] = rewrites.get((kind, exp_id), (None, None))[0]
        original["accepted_wording"] = chosen["claim"] if chosen["status"] == "supported" else None
        accepted["claim_audit"].append(original)
        if chosen["status"] == "supported":
            if kind == "angle":
                accepted["materials"].append({"experience_id": exp_id,
                                               "angle": chosen["claim"],
                                               "evidence_quote": quote})
            else:
                accepted["thesis_claim"] = chosen["claim"]
                accepted["thesis_evidence_quote"] = quote
        else:
            weak = next((s["text"] for s in original["segments"]
                         if s["status"] != "supported"), claim)
            prefix = f"关于「{titles[exp_id]}」：" if kind == "angle" and exp_id in titles else "关于申请主线："
            questions.append(f"{prefix}「{weak[:100]}」需要什么具体做法、比较依据或结果来支持？")
    if not accepted["claim_audit"] and proposal:
        questions.append("候选论点没有可核查的具体主张，请补充学生事实。")
    return accepted, questions
