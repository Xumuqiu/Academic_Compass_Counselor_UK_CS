"""最小脑暴规则：六要素、顺序追问、差距与证据引用。无模型依赖。"""

from copy import deepcopy

ELEMENTS = {
    "process": "行为过程",
    "knowledge": "运用知识",
    "problem": "遇到的问题",
    "solution": "解决方法",
    "reflection": "个人思考",
    "outcome": "最终收获"
}
QUESTION_ORDER = ("problem", "solution", "reflection")
QUESTIONS = {
    "problem": "在这段经历中，你亲自遇到的一个具体困难是什么？当时卡在哪里？",
    "solution": "针对刚才的困难，你尝试了什么方法？你自己做了哪一步，为什么这样做？",
    "reflection": "这段经历让你对申请专业产生了什么新疑问或思考？如果没有，也可以直接说没有。"
}
UCAS_GUIDANCE = {
    "id": "ucas_2026:q2",
    "label": "UCAS 2026 personal statement · question 2",
    "question": "How have your qualifications and studies helped you to prepare for this course or subject?",
    "question_zh": "你的学历和学习如何帮助你为这门课程或学科做好准备？",
    "focus": "Explain relevant learning and reflection, rather than list activities.",
    "focus_zh": "解释相关学习和反思，而不是罗列活动。",
    "source_url": "https://www.ucas.com/applying/applying-university/writing-your-personal-statement",
    "human_verified": False,
    "scope": "UK-wide UCAS guidance; not a preference claimed by the selected university",
}
GRADE_ORDER = {"A*": 5, "A": 4, "B": 3, "C": 2, "D": 1, "E": 0}


def new_state(case):
    exp = case["student"]["experience"]
    values = {
        "process": ("" if case["student"].get("source") == "uploaded_cv" else "担任") + exp["role"] if exp["role"] else None,
        "knowledge": (", " if case["student"].get("source") == "uploaded_cv" else "、").join(exp["skills"]) if exp["skills"] else None,
        "problem": None,
        "solution": None,
        "reflection": None,
        "outcome": "、".join(exp["outputs"]) if exp["outputs"] else None
    }
    sources = {key: exp["source"] for key in ("process", "knowledge", "outcome") if values[key]}
    return {"values": values, "sources": sources, "skipped": [], "round": 0}


def next_question(state):
    if state["round"] >= len(QUESTION_ORDER):
        return None
    key = QUESTION_ORDER[state["round"]]
    question = QUESTIONS[key]
    question_en = {
        "problem": "What specific difficulty did you personally encounter? Where did you get stuck?",
        "solution": "How did you address that difficulty? What did you personally do, and why?",
        "reflection": "What new questions or reflections did this experience raise about Computer Science?",
    }[key]
    if key == "solution" and not state["values"]["problem"]:
        question = "这段经历里，你自己采取过什么关键行动？具体怎么做，为什么？"
        question_en = "What was one important action you personally took? How and why did you do it?"
    elif key == "solution":
        problem = state["values"]["problem"][:80]
        question = f"你刚提到『{problem}』。你怎么应对？自己做了哪一步，为什么？"
        question_en = f"You mentioned: {problem}. How did you respond, and why?"
    return {"element": key, "label": ELEMENTS[key], "text": question, "text_en": question_en}


def accept_answer(state, answer):
    question = next_question(state)
    if question is None:
        raise ValueError("三轮追问已经完成")
    clean = answer.strip()
    if not clean:
        raise ValueError("请输入回答，或点击「跳过」")
    if len(clean) > 1500:
        raise ValueError("单轮回答最多 1500 字")
    updated = deepcopy(state)
    key = question["element"]
    if clean == "[跳过]":
        updated["skipped"].append(key)
    else:
        updated["values"][key] = clean
        updated["sources"][key] = "dialog:r" + str(updated["round"] + 1)
    updated["round"] += 1
    return updated


def programme_gaps(case):
    subjects = {s["name"].casefold(): s["predicted"] for s in case["student"]["subjects"]}
    gaps = []
    for req in case["programme"]["requirements"]:
        if req["kind"] == "math_grade":
            actual = subjects.get("mathematics")
            if actual is None or GRADE_ORDER.get(actual, -1) < GRADE_ORDER[req["expected"]]:
                gaps.append({"kind": "math_grade", "actual": actual, "expected": req["expected"], "text": f"Mathematics 预估 {actual or '未知'}；示例要求为 {req['expected']}。", "requirement_id": req["id"]})
        elif req["kind"] == "science_subject":
            if not any(name.casefold() in subjects for name in req["accepted"]):
                gaps.append({"kind": "science_subject", "text": "目前档案未列出示例要求中的任一门科学科目。", "requirement_id": req["id"]})
    return gaps


def evidence_text(state):
    return [
        {"element": key, "label": label, "text": state["values"][key], "source": state["sources"].get(key)}
        for key, label in ELEMENTS.items()
    ]


def make_brief(case, state, suggestion=None, model_usage=None):
    evidence = evidence_text(state)
    filled = sum(bool(item["text"]) for item in evidence)
    needed = [ELEMENTS[key] for key in QUESTION_ORDER if not state["values"][key]]
    return {
        "student": case["student"]["label"],
        "experience": case["student"]["experience"]["title"],
        "subjects": case["student"]["subjects"],
        "programme": case["programme"],
        "writing_guidance": UCAS_GUIDANCE,
        "evidence": evidence,
        "completeness": f"{filled}/6",
        "status": "待补充证据" if needed else "可供顾问审阅",
        "missing": needed,
        "gaps": programme_gaps(case),
        "suggestion": suggestion,
        "model_usage": model_usage,
        "notice": "写作角度仅供顾问与学生讨论；不得把未确认的推测写成学生经历。院校要求和 UCAS 指引尚未人工核对；UCAS 指引不是所选学校的专属偏好。"
    }
