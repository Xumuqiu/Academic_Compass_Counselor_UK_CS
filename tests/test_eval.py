"""Checks that evaluation scripts measure calls without needing a real key."""

import unittest
from unittest.mock import patch

from eval.cost import cost_rmb, scenario_totals, SCENARIOS
from eval.run_live import run_case
from eval.run_offline import load_cases


class EvalToolTest(unittest.TestCase):
    def test_cost_uses_each_requests_price_tier(self):
        self.assertAlmostEqual(cost_rmb(1_000_000, 0), 1.2)
        self.assertAlmostEqual(cost_rmb(32_000, 1_000), 0.0072)
        self.assertEqual(scenario_totals(SCENARIOS["structured_cv_one_answer_no_rewrite"])
                         ["estimated_rmb"], 0.00298)

    def test_live_claim_runner_records_provider_usage(self):
        case = load_cases()[0][0]
        review = {"claims": [{"kind": "angle", "experience_id": "exp_1",
                  "claim": case["claim"],
                  "segments": [{"text": case["claim"], "verdict": "supported",
                                "evidence": [{"fact_id": "exp_1:problem:1",
                                              "quote": case["answer"]}]}]}]}
        with patch.dict("os.environ", {"COUNSELOR_PROVIDER": "dashscope", "COUNSELOR_MODEL": "qwen3.7-flash"}), patch("counselor.llm._structured",
                   return_value=(review, {"prompt_tokens": 2500,
                                          "completion_tokens": 900})):
            row = run_case(case, "claim")
        self.assertIsNone(row["error"])
        self.assertEqual(len(row["calls"]), 1)
        self.assertTrue(row["original_claim_published"])
        self.assertAlmostEqual(row["actual_cost_rmb"], 0.00122)


if __name__ == "__main__":
    unittest.main()
