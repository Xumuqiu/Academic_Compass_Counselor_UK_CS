"""Complete, planning-free UK CS brainstorming workflow.

The six elements and three matches follow Navigator's essay/brainstorm module.
All facts remain attached to their CV or dialogue source. The model may propose
writing angles, but cannot add experiences, question IDs or evidence references.
"""

from copy import deepcopy
import json
from pathlib import Path

from .domain import ELEMENTS, GRADE_ORDER

UCAS = json.loads((Path(__file__).resolve().parent.parent / "data" /
                   "ucas_2026.json").read_text(encoding="utf-8"))
PROMPTS = tuple((p["id"], p["question"], p["question_en"])
                for p in UCAS["prompts"])
MATCH_LABELS = {
    "skill_knowledge": "技能与知识匹配",
    "mindset_scenario": "思维与场景匹配",
    "interest_direction": "志趣与方向匹配",
}
ORDER = ("process", "knowledge", "problem", "solution", "reflection", "outcome")
QUESTIONS = {
    "process": "「{title}」从开始到结束，你亲自做了哪些事？",
    "knowledge": "「{title}」中你用到了哪些知识或技能？具体用在了哪一步？",
    "problem": "「{title}」里最具体的一个困难是什么？当时卡在哪里？",
    "solution": "你提到「{problem}」。你尝试过什么办法，为什么选了最后的做法？",
    "reflection": "「{title}」之后，你对计算机科学产生了什么新疑问或想法？",
    "outcome": "「{title}」留下了什么作品、代码、报告或其他可指认的结果？",
}
DEEP = (
    ("concept", "你提到的知识或方法，对应计算机科学的哪个具体问题？你是怎么理解它的？"),
    ("alternative", "回头看这个做法，当时还有什么其他选择？你如何比较它们？"),
    ("limit", "这段经历里，现有做法在什么条件下可能失效？你还想学什么来改进？"),
)


def start_case(cv, programmes):
    """Start a multi-experience case; programmes are trusted whitelist objects."""
    student = cv["student"]
    records = []
    for exp in student["experiences"]:
        values = {
            "process": exp["role"] or None,
            "knowledge": "、".join(exp["skills"]) or None,
            "problem": None, "solution": None, "reflection": None,
            "outcome": "、".join(exp["outputs"]) or None,
        }
        sources = {key: exp["source"] for key, value in values.items() if value}
        fact_items = [{"id": f"{exp['id']}:{key}:0", "element": key,
                       "text": value, "source": exp["source"],
                       "confirmation": "recorded_cv"}
                      for key, value in values.items() if value]
        records.append({"experience_id": exp["id"], "title": exp["title"],
                        "type": exp["type"], "values": values, "sources": sources,
                        "fact_items": fact_items, "skipped": [], "deep": {},
                        "verified": False})
    state = {"case": cv, "programmes": deepcopy(programmes), "records": records,
             "round": 0, "messages": [], "finished": False,
             "result": None, "model_usage": None}
    return state


def _missing(record):
    return [key for key in ORDER if not record["values"][key]
            and key not in record["skipped"]]


def next_question(state):
    """Missing elements first, then professional deep dives, one experience at a time."""
    if state["finished"]:
        return None
    for record in state["records"]:
        exp_id, title = record["experience_id"], record["title"]
        for key in _missing(record):
            if key == "solution" and not record["values"]["problem"]:
                if "problem" not in record["skipped"]:
                    continue
                question = ("「{title}」里有没有你自己想办法完成的关键一步？"
                            "具体怎么做，为什么？").format(title=title)
            elif key == "solution":
                question = QUESTIONS[key].format(
                    problem=record["values"]["problem"][:75])
            else:
                question = QUESTIONS[key].format(title=title)
            return {"id": f"{exp_id}:{key}", "experience_id": exp_id,
                    "experience_title": title, "element": key, "text": question,
                    "why": f"这段经历的「{ELEMENTS[key]}」仍需要学生自己的具体说明"}
        if sum(bool(v) for v in record["values"].values()) >= 3:
            for key, question in DEEP:
                if key not in record["deep"] and f"deep:{key}" not in record["skipped"]:
                    return {"id": f"{exp_id}:deep:{key}", "experience_id": exp_id,
                            "experience_title": title, "element": f"deep:{key}",
                            "text": f"关于「{title}」：{question}",
                            "why": "把已还原的经历与计算机科学的具体问题连接起来"}
    return None


def answer_question(state, answer, parse=None, recorded_question=None):
    """Accept the next question, or a validated frozen turn for controlled evals."""
    question = recorded_question if recorded_question is not None else next_question(state)
    if question is None:
        raise ValueError("当前没有待答问题")
    if recorded_question is not None:
        exp_id, element = question.get('experience_id'), question.get('element')
        valid_elements = set(ORDER) | {f'deep:{key}' for key, _ in DEEP}
        if (state['finished'] or exp_id not in {r['experience_id'] for r in state['records']}
                or element not in valid_elements or question.get('id') != f'{exp_id}:{element}'
                or not isinstance(question.get('text'), str)
                or any(m['question']['id'] == question['id'] for m in state['messages'])):
            raise ValueError('冻结访谈问题无效或重复')
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("请输入回答，或点击跳过")
    if len(answer) > 3000:
        raise ValueError("单轮回答最多 3000 字")
    updated = deepcopy(state)
    record = next(r for r in updated["records"]
                  if r["experience_id"] == question["experience_id"])
    key = question["element"]
    clean = answer.strip()
    if clean in ("[跳过]", "跳过", "skip"):
        record["skipped"].append(key)
    elif key.startswith("deep:"):
        record["deep"][key.split(":", 1)[1]] = {
            "text": clean, "source": f"dialog:r{updated['round'] + 1}"}
        record["fact_items"].append({
            "id": f"{record['experience_id']}:{key}:{updated['round'] + 1}",
            "element": key, "text": clean,
            "source": f"dialog:r{updated['round'] + 1}",
            "confirmation": "student_stated"})
    else:
        # The explicit answer always fills the asked field. In live mode the
        # parser can additionally fill other fields, but only from this answer.
        parsed = parse(question, clean) if parse else {}
        if not isinstance(parsed, dict):
            parsed = {}
        fields = {key: clean}
        for other in ORDER:
            value = parsed.get(other)
            if (other != key and isinstance(value, str) and value.strip()
                    and value.strip() in clean):
                fields[other] = value.strip()
        for field, value in fields.items():
            if record["values"][field]:
                # Keep previous evidence; never erase an earlier statement.
                if value not in record["values"][field]:
                    record["values"][field] += "\n" + value
            else:
                record["values"][field] = value
            record["sources"][field] = f"dialog:r{updated['round'] + 1}"
            record["fact_items"].append({
                "id": f"{record['experience_id']}:{field}:{updated['round'] + 1}",
                "element": field, "text": value,
                "source": f"dialog:r{updated['round'] + 1}",
                "confirmation": "student_stated"})
        record["verified"] = len(clean) >= 18 or record["verified"]
    updated["round"] += 1
    updated["messages"].append({"question": question, "answer": clean})
    return updated


def progress(state):
    total = len(state["records"]) * 9
    if not total:
        return 0.0
    filled = sum(sum(bool(v) for v in r["values"].values()) + len(r["deep"])
                 for r in state["records"])
    return round(filled / total, 2)


def programme_gaps(state):
    subjects = {s["name"].casefold(): s["predicted"]
                for s in state["case"]["student"]["subjects"]}
    gaps = []
    for programme in state["programmes"]:
        for req in programme["requirements"]:
            if req["kind"] == "math_grade":
                actual = subjects.get("mathematics")
                if actual is None or GRADE_ORDER.get(actual, -1) < GRADE_ORDER[req["expected"]]:
                    gaps.append({"programme_id": programme["id"],
                                 "requirement_id": req["id"], "kind": req["kind"],
                                 "actual": actual, "expected": req["expected"],
                                 "text": f"数学预估 {actual or '未知'}，项目列出的要求为 {req['expected']}"})
            elif req["kind"] == "science_subject":
                if not any(name.casefold() in subjects for name in req["accepted"]):
                    gaps.append({"programme_id": programme["id"],
                                 "requirement_id": req["id"], "kind": req["kind"],
                                 "text": "档案未列出要求中的科学科目"})
    return gaps


def _matches(record):
    v = record["values"]
    out = []
    if v["knowledge"]:
        out.append("skill_knowledge")
    if v["problem"] and v["solution"]:
        out.append("mindset_scenario")
    if v["reflection"]:
        out.append("interest_direction")
    return out


def _prompt_for(record):
    if record["type"] in ("project", "competition", "holistic"):
        return "ucas_2026:q3"
    return "ucas_2026:q2"


def make_result(state, model_output=None):
    """Assemble a full, source-bound brainstorming brief; no study plan."""
    if model_output is not None and not isinstance(model_output, dict):
        raise ValueError("模型素材包格式不正确")
    if model_output is not None and not model_output.get("_claim_guard_passed"):
        model_output = {}
    materials, open_questions = [], []
    all_titles = {r["experience_id"]: r["title"] for r in state["records"]}
    raw_proposals = (model_output or {}).get("materials", [])
    if not isinstance(raw_proposals, list):
        raw_proposals = []
    proposals = {item.get("experience_id"): item
                 for item in raw_proposals
                 if isinstance(item, dict)}
    for i, record in enumerate(state["records"], 1):
        v = record["values"]
        facts = [{**item, "label": ELEMENTS.get(item["element"], "专业深挖")}
                 for item in record["fact_items"]]
        supported = _matches(record)
        proposal = proposals.get(record["experience_id"], {})
        quote = proposal.get("evidence_quote", "")
        valid_quote = (isinstance(quote, str) and bool(quote)
                       and any(quote in fact["text"] for fact in facts))
        angle = (proposal.get("angle") if valid_quote else None)
        if not isinstance(angle, str) or not angle.strip():
            angle = (f"探讨「{record['title']}」中本人采取的做法及其思考"
                     if supported else f"「{record['title']}」仍需补充具体经历")
        key_points = [f"{fact['label']}：{fact['text']}" for fact in facts
                      if fact["element"] in ("problem", "solution", "reflection")]
        if not key_points:
            key_points = [f"{fact['label']}：{fact['text']}" for fact in facts[:2]]
        narrative = " ".join(f"{fact['label']}：{fact['text']}。" for fact in facts)
        missing = [ELEMENTS[k] for k in _missing(record)]
        if missing:
            open_questions.append(f"关于「{record['title']}」：请补充{'、'.join(missing)}。")
        status = ("core_usable" if sum(bool(x) for x in v.values()) >= 5 and record["verified"]
                  and supported else "needs_substantiation" if missing
                  else "supplementary_usable")
        prompt_id = _prompt_for(record)
        proof_targets = []
        for key in ("knowledge", "process", "solution", "reflection"):
            if v[key]:
                proof_targets.append({"kind": key, "claim": v[key],
                                      "source": record["sources"].get(key)})
        other_titles = [title for eid, title in all_titles.items()
                        if eid != record["experience_id"]]
        materials.append({
            "id": f"mat_{i}", "experience_id": record["experience_id"],
            "title": record["title"], "prompt_id": prompt_id,
            "match_types": supported, "match_labels": [MATCH_LABELS[k] for k in supported],
            "angle": angle, "evidence_quote": quote if valid_quote else None,
            "evidence": facts, "key_points": key_points[:4],
            "narrative": narrative,
            "usage": f"可作为 {prompt_id} 的候选素材；按学生能讲清的细节决定篇幅。",
            "adcom_view": ["可看到学生本人承担的工作与后续思考"
                            if v["reflection"] else "目前主要能看到活动参与和技能，思考仍需追问"],
            "other_uses": ["推荐信可请知情老师核对本人贡献；面试可追问做法与取舍。"],
            "pairing": other_titles[0] if other_titles else None,
            "guide_note": (f"适合围绕{angle}与学生继续核实。"
                           "写作时只使用上方已记录的事实；空缺项留待追问。"),
            "translated_positioning": (v["reflection"] or v["knowledge"] or None),
            "deep_dive": deepcopy(record["deep"]),
            "missing": missing, "status": status,
            "proof_targets": proof_targets,
            "caveats": (["细节尚未经过充分追问"] if not record["verified"] else []) +
                       (["仍有六要素空缺"] if missing else []),
            "sources": deepcopy(record["sources"]),
            "suggested_points": [],
        })
    sections = []
    for prompt_id, zh, en in PROMPTS:
        ids = [m["id"] for m in materials if m["prompt_id"] == prompt_id]
        if prompt_id.endswith(":q1"):
            ids = [m["id"] for m in materials if m["match_types"] and
                   "interest_direction" in m["match_types"]][:2]
        sections.append({"prompt_id": prompt_id, "question": zh,
                         "question_en": en, "material_ids": ids,
            "strategy": ("从学生已记录的经历与反思出发，解释与计算机科学的关系。"
                                      if ids else "当前证据不足，先补充相应经历与思考。")})
    claim = (model_output or {}).get("thesis_claim")
    thesis_quote = (model_output or {}).get("thesis_evidence_quote")
    valid_thesis_quote = (isinstance(thesis_quote, str) and bool(thesis_quote)
                          and any(thesis_quote in fact["text"]
                                  for m in materials for fact in m["evidence"]))
    if not valid_thesis_quote or not isinstance(claim, str) or not claim.strip():
        claim = "候选主线：从已记录的经历中寻找对计算机科学的具体兴趣与持续探索"
    cognition = any(r["values"]["reflection"] or r["deep"].get("concept")
                    for r in state["records"])
    connection = any(m["match_types"] for m in materials)
    growth = sum(bool(r["values"]["reflection"]) for r in state["records"]) >= 2
    result = {
        "student": state["case"]["student"]["label"],
        "programmes": deepcopy(state["programmes"]),
        "subjects": deepcopy(state["case"]["student"]["subjects"]),
        "prompt_set_id": "ucas_2026", "prompts": [
            {"id": p[0], "question": p[1], "question_en": p[2]} for p in PROMPTS],
        "writing_guidance": deepcopy(UCAS),
        "thesis_claim": claim, "sections": sections, "materials": materials,
        "claim_audit": deepcopy((model_output or {}).get("claim_audit", [])),
        "open_questions": open_questions,
        "checks": {
            "professional_cognition": ("已有至少一段本人反思或专业问题说明；需核对其学术准确性。"
                                      if cognition else "尚缺学生本人对计算机科学问题的具体理解。"),
            "connection": ("至少一段经历具备可指认的知识、方法或兴趣匹配；仍需核对相关性。"
                           if connection else "经历与目标专业的具体连接尚未建立。"),
            "growth": ("多段经历均记录了个人反思；可进一步核对真实的递进关系。"
                       if growth else "尚不足以确认从探索到深化的递进轨迹。"),
        },
        "programme_gaps": programme_gaps(state),
        "mode": "live_model" if model_output else "demo_template",
        "notice": "这是头脑风暴素材包，不是个人陈述成稿；待探讨内容不得写成学生事实。",
    }
    # Model output can organise confirmed facts, but cannot introduce unknown
    # experience IDs, prompt IDs or source quotes into the deliverable.
    if model_output:
        valid_ids = {m["id"] for m in materials}
        for supplied in model_output.get("sections", []):
            if not isinstance(supplied, dict):
                continue
            target = next((s for s in sections if s["prompt_id"] == supplied.get("prompt_id")), None)
            if target is None:
                continue
            refs = supplied.get("material_ids", [])
            if isinstance(refs, list) and all(ref in valid_ids for ref in refs):
                target["material_ids"] = refs
            if isinstance(supplied.get("strategy"), str):
                target["strategy"] = supplied["strategy"]
        for proposal in model_output.get("materials", []):
            if not isinstance(proposal, dict):
                continue
            mat = next((m for m in materials if m["experience_id"] == proposal.get("experience_id")), None)
            if mat is None or not mat["evidence_quote"]:
                continue
            for key in ("guide_note", "translated_positioning"):
                if isinstance(proposal.get(key), str) and proposal[key].strip():
                    mat[key] = proposal[key].strip()
            # Narrative is assembled from sourced answers above, never copied
            # from free model prose.
    return result
