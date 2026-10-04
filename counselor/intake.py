"""Standalone multi-experience CV intake for the counselor workflow.

JSON is accepted without a model. TXT/DOCX/PDF text is scrubbed before it is
sent to the configured model for extraction. No uploaded document is retained.
"""

import base64
import json
import re
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

from .cv import _string, _strings
from .domain import GRADE_ORDER

MAX_FILE_BYTES = 5_000_000
MAX_EXPERIENCES = 30
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def normalize_cv(cv):
    """Validate a multi-experience high-school CV without inventing fields."""
    if not isinstance(cv, dict) or not isinstance(cv.get("student"), dict):
        raise ValueError("CV 必须包含 student 对象")
    student = cv["student"]
    subjects = student.get("subjects", [])
    if not isinstance(subjects, list) or len(subjects) > 20:
        raise ValueError("student.subjects 必须是最多 20 项的列表")
    clean_subjects = []
    for i, subject in enumerate(subjects, 1):
        if not isinstance(subject, dict):
            raise ValueError(f"subjects 第 {i} 项必须是对象")
        name = _string(subject.get("name"), f"subjects 第 {i} 项 name", limit=80)
        grade = _string(subject.get("predicted"), f"subjects 第 {i} 项 predicted", limit=4).upper()
        if grade not in GRADE_ORDER:
            raise ValueError("predicted 需为 A*、A、B、C、D 或 E")
        clean_subjects.append({"name": name, "predicted": grade})

    raw = student.get("experiences")
    if raw is None and student.get("experience") is not None:
        raw = [student["experience"]]
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_EXPERIENCES:
        raise ValueError("student.experiences 必须包含 1 至 30 段经历")
    experiences = []
    for i, exp in enumerate(raw, 1):
        if not isinstance(exp, dict):
            raise ValueError(f"experiences 第 {i} 项必须是对象")
        title = _string(exp.get("title"), f"experiences 第 {i} 项 title")
        role = _string(exp.get("role", ""), "role", required=False, limit=500)
        skills = _strings(exp.get("skills", []), "skills")
        outputs = _strings(exp.get("outputs", []), "outputs")
        if not (role or skills or outputs):
            raise ValueError(f"经历「{title}」至少填写 role、skills 或 outputs 之一")
        category = exp.get("type", "academic")
        if category not in ("academic", "project", "competition", "reading", "holistic"):
            raise ValueError(f"经历「{title}」的 type 不在允许范围内")
        experiences.append({
            "id": f"exp_{i}", "title": title, "role": role,
            "skills": skills, "outputs": outputs, "type": category,
            "source": _string(exp.get("source", f"cv:experience:{i}"),
                              "source", limit=100),
        })
    return {
        "student": {
            "id": _string(student.get("id", "student"), "student.id", limit=80),
            "label": _string(student.get("label", "未命名学生"), "student.label"),
            "subjects": clean_subjects, "experiences": experiences,
        }
    }


def scrub_personal_text(text):
    """Remove common identifiers before a document reaches the model."""
    patterns = (
        r"[\w.+-]+@[\w-]+\.[\w.-]+",
        r"(?<!\d)1[3-9]\d{9}(?!\d)",
        r"\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b",
        r"(?:姓名|学生姓名|Name|学校名称|就读学校|School|地址|Address)\s*[:：]\s*[^\n]{1,70}",
    )
    for pattern in patterns:
        text = re.sub(pattern, "[已脱敏]", text, flags=re.IGNORECASE)
    return text


def document_text(filename, encoded):
    """Extract readable text from an uploaded TXT, DOCX or PDF."""
    if not isinstance(encoded, str):
        raise ValueError("文件内容必须是 base64 文字")
    try:
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("文件 base64 内容无效") from exc
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("文件必须非空且不超过 5 MB")
    suffix = filename.lower().rsplit(".", 1)[-1] if isinstance(filename, str) else ""
    if suffix == "txt":
        text = data.decode("utf-8-sig")
    elif suffix == "docx":
        try:
            with ZipFile(BytesIO(data)) as archive:
                root = ET.fromstring(archive.read("word/document.xml"))
        except (BadZipFile, KeyError, ET.ParseError) as exc:
            raise ValueError("DOCX 文件无法解析") from exc
        paragraphs = []
        for paragraph in root.iter(W + "p"):
            line = "".join(node.text or "" for node in paragraph.iter(W + "t"))
            if line.strip():
                paragraphs.append(line)
        text = "\n".join(paragraphs)
    elif suffix == "pdf":
        try:
            import pymupdf
        except ImportError:
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise RuntimeError("PDF 提取需要安装 requirements.txt 中的 pypdf") from exc
            try:
                reader = PdfReader(BytesIO(data))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as exc:
                raise ValueError("PDF 文件无法解析") from exc
        else:
            try:
                with pymupdf.open(stream=data, filetype="pdf") as doc:
                    text = "\n".join(page.get_text() for page in doc)
            except Exception as exc:
                raise ValueError("PDF 文件无法解析") from exc
    else:
        raise ValueError("仅支持 JSON、TXT、DOCX、PDF 文件")
    if len(text.strip()) < 40:
        raise ValueError("文件没有足够的可提取文字；扫描版 PDF 请改用文字版或结构化 JSON")
    return scrub_personal_text(text[:100_000])


def cv_from_document(filename, encoded, extract_cv):
    """Model extraction is injected so tests can verify the full path offline."""
    text = document_text(filename, encoded)
    cv = extract_cv(text)
    return normalize_cv(cv)
