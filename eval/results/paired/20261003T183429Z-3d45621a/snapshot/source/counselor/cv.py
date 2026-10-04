"""Validate a small structured CV and combine it with the fixed demo programme.

Uploaded data lives only in the session memory. This module never reads arbitrary
filesystem paths or treats CV text as trusted instructions.
"""

from copy import deepcopy

from .domain import GRADE_ORDER


def _string(value, field, required=True, limit=200):
    if not isinstance(value, str):
        raise ValueError(f"{field} 必须是文字")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} 不能为空")
    if len(value) > limit:
        raise ValueError(f"{field} 最多 {limit} 字")
    return value


def _strings(value, field):
    if not isinstance(value, list) or len(value) > 10:
        raise ValueError(f"{field} 必须是最多 10 项的列表")
    return [_string(item, f"{field} 条目", limit=150) for item in value]


def case_from_cv(cv, demo_case):
    """Return a normalized per-session case or raise an actionable validation error."""
    if not isinstance(cv, dict) or not isinstance(cv.get("student"), dict):
        raise ValueError("CV 必须包含 student 对象")
    student = cv["student"]
    exp = student.get("experience")
    if not isinstance(exp, dict):
        raise ValueError("student.experience 必须是对象")
    subjects = student.get("subjects", [])
    if not isinstance(subjects, list) or len(subjects) > 20:
        raise ValueError("student.subjects 必须是最多 20 项的列表")
    clean_subjects = []
    for index, subject in enumerate(subjects, 1):
        if not isinstance(subject, dict):
            raise ValueError(f"subjects 第 {index} 项必须是对象")
        name = _string(subject.get("name"), f"subjects 第 {index} 项 name", limit=80)
        grade = _string(subject.get("predicted"), f"subjects 第 {index} 项 predicted", limit=4).upper()
        if grade not in GRADE_ORDER:
            raise ValueError(f"subjects 第 {index} 项 predicted 需为 A*、A、B、C、D 或 E")
        clean_subjects.append({"name": name, "predicted": grade})
    case = deepcopy(demo_case)
    case["student"] = {
        "id": _string(student.get("id", "uploaded_student"), "student.id", limit=80),
        "label": _string(student.get("label"), "student.label"),
        "source": "uploaded_cv",
        "subjects": clean_subjects,
        "experience": {
            "id": "uploaded_experience",
            "title": _string(exp.get("title"), "student.experience.title"),
            "source": "uploaded_cv:experience",
            "role": _string(exp.get("role", ""), "student.experience.role", required=False),
            "skills": _strings(exp.get("skills", []), "student.experience.skills"),
            "outputs": _strings(exp.get("outputs", []), "student.experience.outputs"),
        },
    }
    experience = case["student"]["experience"]
    if not (experience["role"] or experience["skills"] or experience["outputs"]):
        raise ValueError("经历至少填写 role、skills 或 outputs 中的一项，作为可追溯证据")
    return case
