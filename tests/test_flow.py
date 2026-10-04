"""验证最小链路的规则、证据来源与提前结束分支。"""

import unittest
from unittest.mock import patch
import json
from io import BytesIO

from counselor.data import load_case
from counselor.domain import accept_answer, make_brief, new_state, next_question, programme_gaps
from counselor.llm import suggest_angle


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.case = load_case()
        self.state = new_state(self.case)

    def test_three_answers_reach_reviewable_card(self):
        for answer in ("数据记录不完整", "我补测了缺失时段", "想进一步学习如何处理缺失值"):
            self.state = accept_answer(self.state, answer)
        self.assertIsNone(next_question(self.state))
        brief = make_brief(self.case, self.state)
        self.assertEqual(brief["status"], "可供顾问审阅")
        self.assertEqual(brief["completeness"], "6/6")
        self.assertEqual(brief["evidence"][2]["source"], "dialog:r1")

    def test_skip_and_early_finish_keep_missing_evidence_visible(self):
        self.state = accept_answer(self.state, "[跳过]")
        brief = make_brief(self.case, self.state)
        self.assertEqual(brief["status"], "待补充证据")
        self.assertIsNone(brief["evidence"][2]["text"])
        self.assertIn("遇到的问题", brief["missing"])

    def test_deterministic_requirements_show_two_gaps(self):
        gaps = programme_gaps(self.case)
        self.assertEqual({g["requirement_id"] for g in gaps},
                         {"manchester_cs_ug:req_02", "manchester_cs_ug:req_03"})
        bristol = load_case("bristol_cs_ug")
        self.assertEqual({g["requirement_id"] for g in programme_gaps(bristol)},
                         {"bristol_cs_ug:req_02"})

    def test_demo_angle_has_both_languages(self):
        with patch.dict("os.environ", {"COUNSELOR_MODE": "demo"}):
            angle, usage = suggest_angle(self.case, self.state)
        self.assertTrue(angle["angle_zh"].startswith("讨论候选："))
        self.assertTrue(angle["angle_en"].startswith("Discussion idea:"))
        self.assertIsNone(usage)

    def test_live_model_dangling_quote_is_blocked(self):
        payload = {"choices": [{"message": {"content": json.dumps({
            "angle_zh": "讨论候选：学生解决了一个不存在的问题",
            "angle_en": "Discussion idea: The student solved a nonexistent problem.",
            "evidence_quote": "学生获得了国家一等奖"
        }, ensure_ascii=False)}}]}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self):
                return BytesIO(json.dumps(payload, ensure_ascii=False).encode()).read()

        with patch.dict("os.environ", {"COUNSELOR_MODE": "live", "COUNSELOR_PROVIDER": "dashscope", "DASHSCOPE_API_KEY": "test-only"}), \
                patch("counselor.llm.urlopen", return_value=FakeResponse()):
            with self.assertRaisesRegex(RuntimeError, "引用未出现在学生证据中"):
                suggest_angle(self.case, self.state)

    def test_solution_question_uses_previous_answer_and_skip_is_safe(self):
        followup = next_question(accept_answer(self.state, "采样数据缺失"))
        self.assertIn("采样数据缺失", followup["text"])
        skipped = next_question(accept_answer(self.state, "[跳过]"))
        self.assertNotIn("刚才的困难", skipped["text"])

    def test_ucas_guidance_not_claimed_as_school_preference(self):
        brief = make_brief(self.case, self.state)
        self.assertIn("not a preference", brief["writing_guidance"]["scope"])


if __name__ == "__main__":
    unittest.main()
