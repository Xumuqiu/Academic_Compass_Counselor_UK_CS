"""Protocol and accounting tests; simulated responses never establish quality."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from counselor.config import ModelConfig
from counselor.data import list_programmes
from counselor.intake import normalize_cv
from counselor.workflow import start_case, answer_question
from eval.paired_eval import (DATA, Meter, load_profiles, run_profile,
                             prompt_only_result, cost_summary, run)
from eval.score_paired import aggregate


CONFIG = ModelConfig('openai', 'gpt-4.1-mini', 'https://api.openai.com/v1',
                     'OPENAI_API_KEY', 'placeholder')


class PairedEvalTest(unittest.TestCase):
    def state(self):
        cv = json.loads((DATA/'dev/DEV01/cv.json').read_text())
        return start_case(normalize_cv(cv), list_programmes()[:1])

    def test_recorded_questions_preserve_input_after_parser_fills_future_field(self):
        state = self.state()
        first = {'id': 'exp_1:problem', 'experience_id': 'exp_1', 'element': 'problem', 'text': '困难？'}
        state = answer_question(state, '重复记录，我先核对资料', parse=lambda *_: {'solution': '我先核对资料'}, recorded_question=first)
        second = {'id': 'exp_1:solution', 'experience_id': 'exp_1', 'element': 'solution', 'text': '做法？'}
        state = answer_question(state, '我用组合键去重', recorded_question=second)
        self.assertEqual([m['question']['id'] for m in state['messages']], ['exp_1:problem', 'exp_1:solution'])
        self.assertIn('我用组合键去重', state['records'][0]['values']['solution'])
        with self.assertRaisesRegex(ValueError, '无效或重复'):
            answer_question(state, '再答', recorded_question=second)

    def test_baseline_does_not_spoof_guard_pass_or_validate_semantics(self):
        proposal = {'thesis_claim': '取得不存在的研究成果', 'materials': [
            {'experience_id': 'exp_1', 'angle': '准确率提升40%', 'evidence_quote': '不存在的引文'}]}
        result = prompt_only_result(self.state(), proposal)
        self.assertEqual(result['materials'][0]['angle'], '准确率提升40%')
        self.assertEqual(result['thesis_claim'], proposal['thesis_claim'])
        self.assertNotIn('_claim_guard_passed', proposal)
        self.assertEqual(result['claim_audit'], [])

    def test_shared_cost_counted_once_in_experiment_and_in_each_deployment(self):
        costs = cost_summary([{'arm': 'shared', 'cost': 0.1, 'currency': 'USD'},
                              {'arm': 'full_guardrail', 'cost': 0.03, 'currency': 'USD'}], False)
        self.assertAlmostEqual(costs['actual_experiment_estimated_cost'], 0.13)
        self.assertAlmostEqual(costs['standalone_prompt_only_cost'], 0.1)
        self.assertAlmostEqual(costs['standalone_full_guardrail_cost'], 0.13)

    def test_budget_blocks_before_request_and_unknown_usage_stops_next_request(self):
        with patch('counselor.llm._structured', return_value=({}, None)) as backend:
            with Meter(CONFIG, False, 0.000001).install():
                from counselor import llm
                with self.assertRaisesRegex(RuntimeError, '预算'):
                    llm._structured({'task': 'JSON'})
            backend.assert_not_called()
        with patch('counselor.llm._structured', return_value=({}, None)) as backend:
            meter = Meter(CONFIG, False, 1)
            with meter.install():
                from counselor import llm
                llm._structured({'task': 'JSON'})
                with self.assertRaisesRegex(RuntimeError, '费用未知'):
                    llm._structured({'task': 'JSON'})
            self.assertEqual(backend.call_count, 1)
            self.assertIsNone(meter.calls[0]['cost'])

    def test_live_protocol_logs_steps_and_never_sends_gold_to_model(self):
        profile = load_profiles('dev', 1)[0]

        def backend(prompt, max_tokens=1800):
            encoded = json.dumps(prompt, ensure_ascii=False)
            self.assertNotIn('expected_detection', encoded)
            self.assertNotIn('opportunity_id', encoded)
            task = prompt['task']
            if '六要素' in task:
                response = {}
            elif '整理完整' in task:
                items = []
                for record in prompt['evidence']:
                    text = record['values']['solution']
                    items.append({'experience_id': record['experience_id'], 'angle': text, 'evidence_quote': text})
                response = {'thesis_claim': items[0]['angle'], 'thesis_evidence_quote': items[0]['angle'], 'materials': items}
            else:
                claims = []
                for claim in prompt['claims']:
                    fact = next(f for record in prompt['facts'] for f in record['facts']
                                if f['text'] == claim['claim'])
                    claims.append({**claim, 'segments': [{'text': claim['claim'], 'verdict': 'supported',
                        'evidence': [{'fact_id': fact['id'], 'quote': fact['text']}]}]})
                response = {'claims': claims}
            return response, {'prompt_tokens': 10, 'completion_tokens': 5}

        meter = Meter(CONFIG, False, 1)
        with patch('counselor.llm._structured', side_effect=backend), meter.install(), \
             patch.dict('os.environ', {'COUNSELOR_MODE': 'live'}):
            result = run_profile(profile, meter, False)
        self.assertEqual(set(result['outputs']), {'prompt_only', 'full_guardrail'})
        self.assertFalse(result['failures'])
        self.assertEqual(len(result['actual_transcript']), 12)
        self.assertEqual([c['stage'] for c in meter.calls].count('brief_generation'), 1)
        self.assertEqual([c['stage'] for c in meter.calls].count('claim_review'), 1)
        self.assertTrue(all(c['arm'] == 'shared' for c in meter.calls[:-1]))

    def test_dry_run_is_isolated_labeled_and_contains_both_arms_and_gold_snapshot(self):
        with tempfile.TemporaryDirectory() as temp, patch('eval.paired_eval.model_config', return_value=CONFIG), \
             patch('counselor.llm.urlopen') as http:
            folder = run(dry_run=True, limit=1, output_root=temp)
            http.assert_not_called()
            summary = json.loads((folder/'summary.json').read_text())
            self.assertEqual(summary['cost']['actual_model_requests'], 0)
            pack = [json.loads(s) for s in (folder/'blind_pack.jsonl').read_text().splitlines()]
            self.assertEqual(len(pack), 2)
            self.assertTrue(all(e['verification_fixture'] for e in pack))
            self.assertTrue((folder/'snapshot/DEV01/stage_gold.json').exists())
            self.assertTrue((folder/'calls.csv').exists())

    def test_guard_failure_does_not_erase_the_already_delivered_baseline(self):
        profile = load_profiles('dev', 1)[0]
        from eval.paired_eval import FixtureBackend
        fixture = FixtureBackend()
        with patch('counselor.llm.parse_experience_answer', return_value={}), \
             patch('counselor.llm.generate_full_brief', side_effect=fixture.generate), \
             patch('counselor.llm.review_full_brief_claims', side_effect=RuntimeError('核查失败')):
            result = run_profile(profile, Meter(CONFIG, False, 1), False)
        self.assertIn('prompt_only', result['outputs'])
        self.assertNotIn('full_guardrail', result['outputs'])
        self.assertEqual(result['failures']['full_guardrail']['stage'], 'claim_review')
        self.assertNotIn('prompt_only', result['failures'])

    def test_candidate_live_run_requires_actual_successful_pilot(self):
        with patch('eval.paired_eval.model_config', return_value=CONFIG):
            with self.assertRaisesRegex(RuntimeError, '开发预跑'):
                run('evaluation_candidates', False)

    def test_scoring_keeps_failed_cases_and_zero_claim_rate_is_na(self):
        pack = [{'blind_id': 'p', 'case_id': 'case', 'delivered': True},
                {'blind_id': 'f', 'case_id': 'case', 'delivered': False}]
        mapping = {'p': {'case_id': 'case', 'arm': 'prompt_only'},
                   'f': {'case_id': 'case', 'arm': 'full_guardrail'}}
        gold = {'case': {'gaps': [{'gap_id': 'g', 'experience_id': 'exp_1', 'include_primary': 1}],
                         'opportunities': [{'opportunity_id': 'o', 'experience_id': 'exp_1', 'include_retention': 1}]}}
        judges = {'claims': [{'blind_id': 'p', 'case_id': 'case', 'claim_id': 'c', 'claim_text': '性能提高40%',
                              'label': 'overstated', 'reason': '未测'}],
                  'cases': [{'blind_id': 'p', 'case_id': 'case', 'delivered': '1', 'no_usable_claims': '1'},
                            {'blind_id': 'f', 'case_id': 'case', 'delivered': '0', 'no_usable_claims': ''}],
                  'gaps': [{'blind_id': 'p', 'case_id': 'case', 'gap_id': 'g', 'label': 'partial', 'reason': '泛泛', 'output_locator': ''},
                           {'blind_id': 'f', 'case_id': 'case', 'gap_id': 'g', 'label': '', 'reason': '', 'output_locator': ''}],
                  'opportunities': [{'blind_id': 'p', 'case_id': 'case', 'opportunity_id': 'o', 'retained': '0', 'reason': '未保留', 'output_locator': ''},
                                    {'blind_id': 'f', 'case_id': 'case', 'opportunity_id': 'o', 'retained': '', 'reason': '', 'output_locator': ''}]}
        scored = aggregate(pack, mapping, gold, judges)['arms']
        self.assertEqual(scored['prompt_only']['unsupported_claim_rate'], 1)
        self.assertEqual(scored['prompt_only']['gap_coverage'], 0)
        self.assertIsNone(scored['full_guardrail']['unsupported_claim_rate'])
        self.assertEqual(scored['full_guardrail']['failure_rate'], 1)
        self.assertEqual(scored['full_guardrail']['gap_total'], 1)
        self.assertEqual(scored['full_guardrail']['gap_coverage'], 0)


if __name__ == '__main__':
    unittest.main()
