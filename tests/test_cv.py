"""Verify uploaded CV validation, per-session evidence and the HTTP path."""

import json
import unittest
from io import BytesIO
from unittest.mock import patch

from counselor.cv import case_from_cv
from counselor.data import load_case
from counselor.domain import make_brief, new_state
from counselor.server import Handler


CV = {
    "student": {
        "id": "test_02",
        "label": "Fictional student B",
        "subjects": [{"name": "Mathematics", "predicted": "A*"}, {"name": "Physics", "predicted": "A"}],
        "experience": {"title": "School coding club", "role": "tester", "skills": ["Python"], "outputs": ["prototype"]},
    }
}


class CvTest(unittest.TestCase):
    def test_uploaded_cv_changes_evidence_and_gaps(self):
        case = case_from_cv(CV, load_case())
        brief = make_brief(case, new_state(case))
        self.assertEqual(brief["experience"], "School coding club")
        self.assertEqual(brief["evidence"][0]["text"], "tester")
        self.assertEqual(brief["evidence"][0]["source"], "uploaded_cv:experience")
        self.assertEqual(brief["gaps"], [])

    def test_invalid_cv_rejected_without_changing_demo(self):
        with self.assertRaisesRegex(ValueError, "predicted"):
            case_from_cv({"student": {**CV["student"], "subjects": [{"name": "Mathematics", "predicted": "Z"}]}}, load_case())
        self.assertEqual(load_case()["student"]["label"], "虚构学生 A（高二，A-Level）")

    def test_api_uploaded_and_demo_sessions_are_separate(self):
        def post(path, body):
            payload = json.dumps(body).encode()
            handler = Handler.__new__(Handler)
            handler.path = path
            handler.headers = {"Content-Length": str(len(payload))}
            handler.rfile = BytesIO(payload)
            result = {}
            handler.respond = lambda status, data: result.update(status=status, data=data)
            handler.do_POST()
            return result

        with patch.dict("os.environ", {"COUNSELOR_MODE": "demo"}):
            uploaded = post("/api/start", {"cv": CV})["data"]
            demo = post("/api/start", {})["data"]
            self.assertFalse(uploaded["is_demo"])
            self.assertTrue(demo["is_demo"])
            self.assertNotEqual(uploaded["student"], demo["student"])
            self.assertEqual(post("/api/finish", {"session_id": uploaded["session_id"]})["data"]["gaps"], [])
            self.assertEqual(len(post("/api/finish", {"session_id": demo["session_id"]})["data"]["gaps"]), 2)
            self.assertEqual(post("/api/start", {"cv": {"student": {"label": "Bad"}}})["status"], 400)

    def test_programme_selection_changes_rule_result(self):
        def post(body):
            payload = json.dumps(body).encode()
            handler = Handler.__new__(Handler)
            handler.path = "/api/start"
            handler.headers = {"Content-Length": str(len(payload))}
            handler.rfile = BytesIO(payload)
            result = {}
            handler.respond = lambda status, data: result.update(status=status, data=data)
            handler.do_POST()
            return result

        bristol = post({"cv": CV, "program_id": "bristol_cs_ug"})
        self.assertEqual(bristol["status"], 200)
        self.assertEqual(bristol["data"]["programme"]["id"], "bristol_cs_ug")
        self.assertEqual(post({"program_id": "unknown"})["status"], 400)


if __name__ == "__main__":
    unittest.main()
