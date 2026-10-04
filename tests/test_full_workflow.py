"""End-to-end checks for the planning-free brainstorming product path."""

import base64
import json
import unittest
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from counselor.data import list_programmes
from counselor.document import export_docx
from counselor.intake import cv_from_document, document_text, normalize_cv
from counselor.server import Handler
from counselor.workflow import answer_question, make_result, next_question, start_case
from counselor.claim_check import checked_proposals, propose_narrowings


CV = {"student": {
    "label": "虚构学生 Tracy", "subjects": [
        {"name": "Mathematics", "predicted": "A*"},
        {"name": "Physics", "predicted": "A"}],
    "experiences": [
        {"title": "机器人竞赛", "role": "调试传感器与路线", "skills": ["传感器控制"],
         "outputs": ["比赛作品"], "type": "competition"},
        {"title": "电脑配件网站", "role": "设计功能并修改页面", "skills": ["HTML"],
         "outputs": ["网站原型"], "type": "project"},
    ]}}


def post(path, body):
    payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler = Handler.__new__(Handler)
    handler.path = path
    handler.headers = {"Content-Length": str(len(payload))}
    handler.rfile = BytesIO(payload)
    result = {}
    handler.respond = lambda status, data: result.update(status=status, data=data)
    handler.do_POST()
    return result


class FullWorkflowTest(unittest.TestCase):
    def test_skipped_deep_question_advances_and_interview_terminates(self):
        state = start_case(normalize_cv(CV), list_programmes()[:1])
        first_id = state["records"][0]["experience_id"]
        seen = []
        for _ in range(18):
            question = next_question(state)
            if question is None:
                break
            seen.append(question["id"])
            state = answer_question(state, "[跳过]")
        self.assertIsNone(next_question(state))
        self.assertEqual(len(seen), len(set(seen)))
        self.assertIn(first_id + ":deep:concept", seen)
        self.assertIn(first_id + ":deep:alternative", seen)
        self.assertIn(first_id + ":deep:limit", seen)

    def test_multi_experience_to_docx_without_plan(self):
        cv = normalize_cv(CV)
        state = start_case(cv, list_programmes())
        self.assertEqual(len(state["records"]), 2)
        self.assertEqual(next_question(state)["experience_id"], "exp_1")
        # Complete one experience, then the selector must move to the second.
        while next_question(state) and next_question(state)["experience_id"] == "exp_1":
            state = answer_question(state, "我根据现场反馈比较方案并记录结果。")
        self.assertEqual(next_question(state)["experience_id"], "exp_2")
        while next_question(state):
            state = answer_question(state, "我自己测试了页面，并反思了用户需求。")
        result = make_result(state)
        self.assertEqual(len(result["materials"]), 2)
        self.assertEqual(len(result["sections"]), 3)
        self.assertTrue(any(x["source"].startswith("dialog:r")
                            for m in result["materials"] for x in m["evidence"]))
        self.assertNotIn("plan", result)
        data = export_docx(result)
        with ZipFile(BytesIO(data)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        self.assertIn("机器人竞赛", xml)
        self.assertIn("电脑配件网站", xml)
        self.assertIn("UCAS 三问写作思路", xml)
        self.assertNotIn("Learning Plan", xml)

    def test_document_intake_scrubs_before_model_and_normalizes_all_experiences(self):
        raw = "Name: Test Student\nEmail: test@example.com\n" + "Project details. " * 8
        encoded = base64.b64encode(raw.encode()).decode()
        seen = {}
        def extractor(text):
            seen["text"] = text
            return CV
        cv = cv_from_document("cv.txt", encoded, extractor)
        self.assertEqual(len(cv["student"]["experiences"]), 2)
        self.assertNotIn("test@example.com", seen["text"])
        self.assertIn("[已脱敏]", seen["text"])

    def test_docx_document_input_is_readable(self):
        stream = BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:p><w:r><w:t>' + ('My project used Python to analyse data. ' * 3) +
                '</w:t></w:r></w:p></w:document>')
        text = document_text("cv.docx", base64.b64encode(stream.getvalue()).decode())
        self.assertIn("My project used Python", text)

    def test_full_http_path_and_export(self):
        with patch.dict("os.environ", {"COUNSELOR_MODE": "demo"}):
            built_in = post("/api/full/start", {"program_ids": ["manchester_cs_ug"]})
            self.assertEqual(built_in["status"], 200)
            self.assertEqual(len(built_in["data"]["records"]), 2)
            start = post("/api/full/start", {"cv": CV, "program_ids": [
                "manchester_cs_ug", "bristol_cs_ug"]})
            self.assertEqual(start["status"], 200)
            sid = start["data"]["session_id"]
            answer = post("/api/full/answer", {"session_id": sid,
                                                 "answer": "现场路线转弯时传感器读数不稳。"})
            self.assertEqual(answer["status"], 200)
            finish = post("/api/full/finish", {"session_id": sid})
            self.assertEqual(finish["status"], 200)
            self.assertEqual(len(finish["data"]["materials"]), 2)
            self.assertNotIn("plan_summary", finish["data"])
            handler = Handler.__new__(Handler)
            handler.path = "/api/full/export/" + sid
            handler.wfile = BytesIO()
            status = []
            handler.send_response = lambda value: status.append(value)
            handler.send_header = lambda *args: None
            handler.end_headers = lambda: None
            handler.do_GET()
            self.assertEqual(status, [200])
            self.assertTrue(handler.wfile.getvalue().startswith(b"PK"))

    def test_model_angle_needs_verbatim_quote(self):
        state = start_case(normalize_cv(CV), list_programmes()[:1])
        result = make_result(state, {"materials": [{
            "experience_id": "exp_1", "angle": "优化了算法性能",
            "evidence_quote": "没有出现在学生材料中的性能测试"
        }]})
        self.assertNotEqual(result["materials"][0]["angle"], "优化了算法性能")

    def test_verbatim_quote_alone_does_not_validate_claim(self):
        state = start_case(normalize_cv(CV), list_programmes()[:1])
        proposed = {"materials": [{"experience_id": "exp_1",
                     "angle": "我优化了算法性能", "evidence_quote": "调试传感器与路线"}],
                    "thesis_claim": "我通过系统优化提升性能",
                    "thesis_evidence_quote": "调试传感器与路线"}
        review = {"claims": [
            {"kind": "angle", "experience_id": "exp_1",
             "claim": "我优化了算法性能", "evidence_quote": "调试传感器与路线",
             "verdict": "overstated"},
            {"kind": "thesis", "experience_id": None,
             "claim": "我通过系统优化提升性能", "evidence_quote": "调试传感器与路线",
             "verdict": "insufficient"}]}
        checked, questions = checked_proposals(state, proposed, review)
        self.assertEqual(checked["materials"], [])
        self.assertNotIn("thesis_claim", checked)
        self.assertEqual(len(questions), 2)

    def test_answer_parser_cannot_add_unspoken_fact(self):
        state = start_case(normalize_cv(CV), list_programmes()[:1])
        answer = "我主要负责调试硬件。"
        updated = answer_question(state, answer, parse=lambda *_: {
            "reflection": "性能下降了百分之四十", "solution": "我主要负责调试硬件"})
        record = updated["records"][0]
        self.assertIsNone(record["values"]["reflection"])
        self.assertIn("我主要负责调试硬件", record["values"]["solution"])

    def test_live_finish_routes_proposal_through_claim_guard(self):
        start = post("/api/full/start", {"cv": CV, "program_ids": ["manchester_cs_ug"]})
        sid = start["data"]["session_id"]
        proposal = {"materials": [{"experience_id": "exp_1",
                    "angle": "优化了算法性能", "evidence_quote": "调试传感器与路线"}]}
        review = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                  "claim": "优化了算法性能", "evidence_quote": "调试传感器与路线",
                  "verdict": "overstated"}]}
        with patch("counselor.server.generate_full_brief", return_value=(proposal, None)), \
             patch("counselor.server.review_full_brief_claims", return_value=(review, None)):
            finish = post("/api/full/finish", {"session_id": sid})
        self.assertEqual(finish["status"], 200)
        self.assertNotEqual(finish["data"]["materials"][0]["angle"], "优化了算法性能")
        self.assertTrue(any("优化了算法性能" in q for q in finish["data"]["open_questions"]))

    def test_fact_sources_survive_multiple_answers_in_one_element(self):
        state = start_case(normalize_cv(CV), list_programmes()[:1])
        state = answer_question(state, "第一次回答提出传感器校准问题。")
        state = answer_question(state, "第二次回答说明我重新校准了传感器。",
                                parse=lambda *_: {"problem": "传感器校准"})
        facts = state["records"][0]["fact_items"]
        self.assertEqual(facts[0]["confirmation"], "recorded_cv")
        self.assertTrue(any(f["source"] == "dialog:r1" for f in facts))
        self.assertTrue(any(f["source"] == "dialog:r2" for f in facts))

    def test_every_claim_segment_needs_confirmed_fact(self):
        state = start_case(normalize_cv(CV), list_programmes()[:1])
        state = answer_question(state, "因开发周期有限，我放弃复杂方案，选择先完成可运行版本。")
        fact = next(f for f in state["records"][0]["fact_items"]
                    if f["source"] == "dialog:r1")
        proposal = {"materials": [{"experience_id": "exp_1",
                    "angle": "我比较方案并优化了算法性能",
                    "evidence_quote": "放弃复杂方案"}]}
        review = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                   "claim": proposal["materials"][0]["angle"],
                   "segments": [
                       {"text": "我比较方案并", "verdict": "supported",
                        "evidence": [{"fact_id": fact["id"], "quote": "放弃复杂方案"}]},
                       {"text": "优化了算法性能", "verdict": "overstated", "evidence": []}],
                   "suggested_wording": "我因开发周期作出可行性取舍"}]}
        checked, questions = checked_proposals(state, proposal, review)
        self.assertEqual(checked["materials"], [])
        self.assertEqual(checked["claim_audit"][0]["segments"][1]["status"], "overstated")
        self.assertIn("优化了算法性能", questions[0])
        narrower = propose_narrowings(proposal, review)
        recheck = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                    "claim": "我因开发周期作出可行性取舍",
                    "segments": [{"text": "我因开发周期作出可行性取舍",
                                  "verdict": "supported",
                                  "evidence": [{"fact_id": fact["id"],
                                                "quote": fact["text"]}]}]}]}
        self.assertEqual(narrower["materials"][0]["angle"], recheck["claims"][0]["claim"])
        checked, questions = checked_proposals(state, proposal, review, recheck)
        self.assertEqual(checked["materials"][0]["angle"], "我因开发周期作出可行性取舍")
        self.assertEqual(questions, [])
        result = make_result(state, checked)
        self.assertEqual(result["claim_audit"][0]["status"], "narrowed_supported")
        with ZipFile(BytesIO(export_docx(result))) as archive:
            self.assertIn("论点措辞与事实核查", archive.read("word/document.xml").decode())

    def test_claim_guard_rejects_missing_span_cv_only_number_and_wrong_fact(self):
        state = start_case(normalize_cv(CV), list_programmes()[:1])
        state = answer_question(state, "我比较了两个方案并记录了选择原因。")
        stated = next(f for f in state["records"][0]["fact_items"]
                      if f["source"] == "dialog:r1")
        cv_fact = state["records"][0]["fact_items"][0]
        cases = [
            ("我比较了两个方案并提升了性能", [
                {"text": "我比较了两个方案并", "verdict": "supported",
                 "evidence": [{"fact_id": stated["id"], "quote": stated["text"]}]}],
             "incomplete_segmentation"),
            ("我调试传感器与路线", [
                {"text": "我调试传感器与路线", "verdict": "supported",
                 "evidence": [{"fact_id": cv_fact["id"], "quote": cv_fact["text"]}]}],
             "needs_confirmation"),
            ("我比较了两个方案并提升性能40%", [
                {"text": "我比较了两个方案并提升性能40%", "verdict": "supported",
                 "evidence": [{"fact_id": stated["id"], "quote": stated["text"]}]}],
             "unsupported_measurement"),
            ("我比较了两个方案", [
                {"text": "我比较了两个方案", "verdict": "supported",
                 "evidence": [{"fact_id": "exp_2:process:0", "quote": "设计功能并修改页面"}]}],
             "invalid_reference"),
        ]
        for claim, segments, expected in cases:
            with self.subTest(expected=expected):
                proposal = {"materials": [{"experience_id": "exp_1",
                            "angle": claim, "evidence_quote": stated["text"]}]}
                review = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                           "claim": claim, "segments": segments}]}
                checked, _ = checked_proposals(state, proposal, review)
                self.assertEqual(checked["materials"], [])
                self.assertEqual(checked["claim_audit"][0]["status"], expected)

    def test_http_finish_rechecks_narrowed_wording(self):
        with patch.dict("os.environ", {"COUNSELOR_MODE": "demo"}):
            start = post("/api/full/start", {"cv": CV, "program_ids": ["manchester_cs_ug"]})
            sid = start["data"]["session_id"]
            answer = "因开发周期有限，我放弃复杂方案并记录了选择原因。"
            post("/api/full/answer", {"session_id": sid, "answer": answer})
        proposed = {"materials": [{"experience_id": "exp_1", "angle": "我优化了算法性能",
                     "evidence_quote": "放弃复杂方案"}]}
        first = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                  "claim": "我优化了算法性能",
                  "segments": [{"text": "我优化了算法性能", "verdict": "overstated",
                                "evidence": [], "reason": "没有性能指标"}],
                  "suggested_wording": "我因开发周期有限放弃复杂方案"}]}
        second = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                   "claim": "我因开发周期有限放弃复杂方案",
                   "segments": [{"text": "我因开发周期有限放弃复杂方案",
                                 "verdict": "supported",
                                 "evidence": [{"fact_id": "exp_1:problem:1",
                                               "quote": answer}]}]}]}
        with patch("counselor.server.generate_full_brief", return_value=(proposed, None)), \
             patch("counselor.server.review_full_brief_claims",
                   side_effect=[(first, None), (second, None)]) as reviewer:
            result = post("/api/full/finish", {"session_id": sid})
        self.assertEqual(reviewer.call_count, 2)
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["data"]["materials"][0]["angle"],
                         "我因开发周期有限放弃复杂方案")
        self.assertEqual(result["data"]["claim_audit"][0]["status"],
                         "narrowed_supported")

    def test_anchor_quote_must_belong_to_cited_support(self):
        state = start_case(normalize_cv(CV), list_programmes()[:1])
        state = answer_question(state, "我比较了两个方案并记录了选择原因。")
        cited = next(f for f in state["records"][0]["fact_items"]
                     if f["source"] == "dialog:r1")
        proposal = {"materials": [{"experience_id": "exp_1",
                    "angle": "我比较了两个方案", "evidence_quote": "调试传感器与路线"}]}
        review = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                   "claim": "我比较了两个方案",
                   "segments": [{"text": "我比较了两个方案", "verdict": "supported",
                                 "evidence": [{"fact_id": cited["id"],
                                               "quote": cited["text"]}]}]}]}
        checked, _ = checked_proposals(state, proposal, review)
        self.assertEqual(checked["materials"], [])
        self.assertEqual(checked["claim_audit"][0]["status"], "invalid_reference")


if __name__ == "__main__":
    unittest.main()
