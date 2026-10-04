"""Dependency-free Word export of the brainstorming brief.

The document stops at material and writing guidance. No study plan is included.
"""

from io import BytesIO
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED


def _paragraph(text, style=None, bold_lead=None):
    tag = f'<w:pStyle w:val="{style}"/>' if style else ""
    fonts = '<w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="STHeiti"/>'
    if bold_lead:
        runs = (f'<w:r><w:rPr>{fonts}<w:b/></w:rPr><w:t xml:space="preserve">'
                f'{escape(bold_lead)}</w:t></w:r>'
                f'<w:r><w:rPr>{fonts}</w:rPr><w:t xml:space="preserve">{escape(str(text))}</w:t></w:r>')
    else:
        runs = f'<w:r><w:rPr>{fonts}</w:rPr><w:t xml:space="preserve">{escape(str(text))}</w:t></w:r>'
    return f'<w:p><w:pPr>{tag}</w:pPr>{runs}</w:p>'


def export_docx(result):
    """Return a complete DOCX containing the multi-material brainstorming result."""
    body = [_paragraph("英国本科计算机科学申请头脑风暴素材包", "Title"),
            _paragraph(f"学生：{result['student']}｜申请体系：UCAS 2026"),
            _paragraph(result["notice"]),
            _paragraph("申请主线", "Heading1"),
            _paragraph(result["thesis_claim"]),
            _paragraph("UCAS 三问写作思路", "Heading1")]
    for section in result["sections"]:
        body.append(_paragraph(section["question"], "Heading2"))
        body.append(_paragraph(section["strategy"]))
        titles = [m["title"] for m in result["materials"]
                  if m["id"] in section["material_ids"]]
        if titles:
            body.append(_paragraph("可用素材：" + "、".join(titles)))
    body.append(_paragraph("经历与素材说明", "Heading1"))
    for mat in result["materials"]:
        body.append(_paragraph(mat["title"], "Heading2"))
        body.append(_paragraph("当前状态：" + {
            "core_usable": "核心候选", "supplementary_usable": "补充候选",
            "needs_substantiation": "待补充证据"}.get(mat["status"], mat["status"])))
        body.append(_paragraph("写作角度：" + mat["angle"]))
        if mat["match_labels"]:
            body.append(_paragraph("专业匹配：" + "、".join(mat["match_labels"])))
        if mat["translated_positioning"]:
            body.append(_paragraph("专业转译：" + mat["translated_positioning"]))
        body.append(_paragraph("素材总结", "Heading3"))
        body.append(_paragraph(mat["narrative"] or "尚无可确认的经历细节。"))
        body.append(_paragraph("使用说明", "Heading3"))
        body.append(_paragraph(mat["guide_note"]))
        body.append(_paragraph(mat["usage"], bold_lead="题目用途："))
        if mat.get("pairing"):
            body.append(_paragraph(mat["pairing"], bold_lead="可串联经历："))
        for view in mat.get("adcom_view", []):
            body.append(_paragraph(view, bold_lead="招生官视角："))
        for use in mat.get("other_uses", []):
            body.append(_paragraph(use, bold_lead="其他用途："))
        for point in mat["key_points"]:
            body.append(_paragraph("• " + point))
        body.append(_paragraph("已记录事实与来源", "Heading3"))
        for fact in mat["evidence"]:
            body.append(_paragraph(f"{fact['label']}（{fact['source'] or '来源待确认'}）：{fact['text']}"))
        if mat["missing"]:
            body.append(_paragraph("仍需补充：" + "、".join(mat["missing"])))
        for caveat in mat.get("caveats", []):
            body.append(_paragraph(caveat, bold_lead="使用提醒："))
    body.append(_paragraph("收尾核查", "Heading1"))
    for label, key in (("专业认知", "professional_cognition"),
                       ("经历与专业的结合", "connection"), ("成长轨迹", "growth")):
        body.append(_paragraph(result["checks"][key], bold_lead=label + "："))
    if result.get("claim_audit"):
        body.append(_paragraph("论点措辞与事实核查", "Heading1"))
        statuses = {"supported": "有事实支持", "narrowed_supported": "收窄后有事实支持",
                    "overstated": "表述过强", "insufficient": "证据不足",
                    "contradicted": "与记录冲突", "needs_confirmation": "仅有简历记录，待学生确认",
                    "unsupported_measurement": "数字缺少对应依据",
                    "invalid_reference": "事实引用无效", "review_missing": "核查未完成",
                    "incomplete_segmentation": "论点未完整拆分"}
        for claim in result["claim_audit"]:
            body.append(_paragraph("原论点：" + claim["claim"], "Heading2"))
            body.append(_paragraph("判定：" + statuses.get(claim["status"], claim["status"])))
            if claim.get("accepted_wording"):
                body.append(_paragraph("可用措辞：" + claim["accepted_wording"]))
            elif claim.get("suggested_wording"):
                body.append(_paragraph("待核查的收窄建议：" + claim["suggested_wording"]))
            for segment in claim["segments"]:
                body.append(_paragraph("• " + segment["text"] + " — " +
                                       statuses.get(segment["status"], segment["status"])))
                for anchor in segment["evidence"]:
                    body.append(_paragraph("依据：" + anchor["quote"] +
                                           "（" + anchor["source"] + "）"))
    if result["open_questions"]:
        body.append(_paragraph("待向学生确认", "Heading1"))
        body.extend(_paragraph("• " + q) for q in result["open_questions"])
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + "".join(body) +
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1100" w:right="1150" w:bottom="1100" w:left="1150"/>'
        '</w:sectPr></w:body></w:document>')
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
        '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="STHeiti"/>'
        '<w:sz w:val="21"/></w:rPr><w:pPr><w:spacing w:after="120" w:line="300"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
        '<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="34"/>'
        '</w:rPr><w:pPr><w:spacing w:after="260"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="27"/>'
        '</w:rPr><w:pPr><w:spacing w:before="300" w:after="160"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
        '<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="24"/>'
        '</w:rPr><w:pPr><w:spacing w:before="220" w:after="100"/></w:pPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/>'
        '<w:basedOn w:val="Normal"/><w:rPr><w:b/><w:color w:val="000000"/><w:sz w:val="21"/>'
        '</w:rPr><w:pPr><w:spacing w:before="150" w:after="70"/></w:pPr></w:style>'
        '</w:styles>')
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '</Types>')
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>')
    doc_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        '</Relationships>')
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path, content in (
            ("[Content_Types].xml", content_types), ("_rels/.rels", rels),
            ("word/document.xml", document), ("word/styles.xml", styles),
            ("word/_rels/document.xml.rels", doc_rels),
        ):
            archive.writestr(path, content)
    return output.getvalue()
