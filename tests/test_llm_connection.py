"""Provider routing, local configuration and authentication regressions."""
import json
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from counselor import llm
from counselor.config import model_config, read_settings
from eval.cost import usage_quote


class ConnectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root_patch = patch('counselor.config.ROOT', Path(self.temp.name))
        root_patch.start()
        self.addCleanup(root_patch.stop)
        env_patch = patch.dict(os.environ, {}, clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)

    def response(self, content='{"ok":true}'):
        return BytesIO(json.dumps({'choices': [{'message': {'content': content}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}).encode())

    def test_project_env_local_overrides_file_but_not_process(self):
        root = Path(self.temp.name)
        (root/'.env').write_text('OPENAI_API_KEY="file-placeholder"\nCOUNSELOR_MODE=live\nIGNORED_SETTING=x\n')
        (root/'.env.local').write_text('export OPENAI_API_KEY=local-placeholder # comment\n')
        self.assertEqual(read_settings()['OPENAI_API_KEY'], 'local-placeholder')
        self.assertNotIn('IGNORED_SETTING', read_settings())
        os.environ['OPENAI_API_KEY'] = 'process-placeholder'
        self.assertEqual(model_config().api_key, 'process-placeholder')
        self.assertEqual(model_config().provider, 'openai')
        self.assertNotIn('process-placeholder', repr(model_config()))

    def test_misnamed_key_is_never_sent_to_another_provider(self):
        os.environ.update(COUNSELOR_MODE='live', DASHSCOPE_API_KEY='sk-proj-placeholder')
        with patch('counselor.llm.urlopen') as call:
            with self.assertRaisesRegex(RuntimeError, 'OPENAI_API_KEY'):
                llm._structured({'task': 'JSON'})
            call.assert_not_called()
        os.environ['COUNSELOR_PROVIDER'] = 'dashscope'
        with self.assertRaisesRegex(RuntimeError, '不能发送到 DashScope'):
            model_config()

    def test_openai_request_has_correct_endpoint_parameters_and_key(self):
        os.environ.update(COUNSELOR_MODE='live', OPENAI_API_KEY='openai-placeholder',
                          DASHSCOPE_API_KEY='other-provider-placeholder')
        with patch('counselor.llm.urlopen', return_value=self.response()) as call:
            result, usage = llm._structured({'task': 'JSON'}, max_tokens=32)
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(request.get_header('Authorization'), 'Bearer openai-placeholder')
        self.assertEqual(body['response_format'], {'type': 'json_object'})
        self.assertNotIn('enable_thinking', body)
        self.assertNotIn('extra_body', body)
        self.assertEqual(body['max_tokens'], 32)
        self.assertEqual(result, {'ok': True})
        self.assertEqual(usage['prompt_tokens'], 10)

    def test_dashscope_is_explicit_and_uses_its_own_key(self):
        os.environ.update(COUNSELOR_MODE='live', COUNSELOR_PROVIDER='dashscope',
                          DASHSCOPE_API_KEY='dashscope-placeholder', OPENAI_API_KEY='other-placeholder')
        with patch('counselor.llm.urlopen', return_value=self.response()) as call:
            llm._structured({'task': 'JSON'})
        request = call.call_args.args[0]
        self.assertEqual(request.get_header('Authorization'), 'Bearer dashscope-placeholder')
        self.assertTrue(request.full_url.startswith('https://dashscope.aliyuncs.com/'))
        self.assertFalse(json.loads(request.data)['enable_thinking'])

    def test_wrong_endpoint_and_provider_model_fail_before_request(self):
        os.environ.update(OPENAI_API_KEY='placeholder', OPENAI_BASE_URL='https://dashscope.aliyuncs.com/v1')
        with self.assertRaisesRegex(RuntimeError, '官方端点'):
            model_config()
        del os.environ['OPENAI_BASE_URL']
        os.environ['COUNSELOR_MODEL'] = 'qwen3.7-flash'
        with self.assertRaisesRegex(RuntimeError, '供应商不匹配'):
            model_config()

    def test_auth_error_keeps_code_but_never_echoes_key_or_body(self):
        os.environ.update(COUNSELOR_MODE='live', OPENAI_API_KEY='sensitive-placeholder')
        error = HTTPError('https://api.openai.com/v1/chat/completions', 401, 'Unauthorized', {},
            BytesIO(json.dumps({'error': {'code': 'invalid_api_key',
                                         'message': 'sensitive-placeholder'}}).encode()))
        with patch('counselor.llm.urlopen', side_effect=error):
            with self.assertRaises(RuntimeError) as raised:
                llm._structured({'task': 'JSON'})
        text = str(raised.exception)
        self.assertIn('HTTP 401 (invalid_api_key)', text)
        self.assertNotIn('sensitive-placeholder', text)

    def test_non_object_model_output_is_rejected(self):
        os.environ.update(COUNSELOR_MODE='live', OPENAI_API_KEY='placeholder')
        with patch('counselor.llm.urlopen', return_value=self.response('[]')):
            with self.assertRaisesRegex(RuntimeError, 'JSON 对象'):
                llm._structured({'task': 'JSON'})

    def test_server_uses_live_parser_when_mode_is_only_in_env_file(self):
        from counselor.server import Handler, FULL_SESSIONS
        (Path(self.temp.name)/'.env.local').write_text('COUNSELOR_MODE=live\nOPENAI_API_KEY=placeholder\n')

        def post(path, body):
            data = json.dumps(body).encode()
            handler = Handler.__new__(Handler)
            handler.path = path
            handler.headers = {'Content-Length': str(len(data))}
            handler.rfile = BytesIO(data)
            result = {}
            handler.respond = lambda status, payload: result.update(status=status, data=payload)
            handler.do_POST()
            return result

        started = post('/api/full/start', {})
        self.assertEqual(started['status'], 200)
        sid = started['data']['session_id']
        self.addCleanup(lambda: FULL_SESSIONS.pop(sid, None))
        with patch('counselor.server.parse_experience_answer', return_value={}) as parser:
            response = post('/api/full/answer', {'session_id': sid, 'answer': '输入缺失'})
        self.assertEqual(response['status'], 200)
        parser.assert_called_once()
        self.assertEqual(parser.call_args.args[1], '输入缺失')

    def test_openai_cache_cost_and_unknown_model_are_not_qwen_rmb(self):
        usage = {'prompt_tokens': 1000, 'completion_tokens': 100,
                 'prompt_tokens_details': {'cached_tokens': 500}}
        quote = usage_quote(usage, 'openai', 'gpt-4.1-mini')
        self.assertEqual(quote['currency'], 'USD')
        self.assertAlmostEqual(quote['cost'], 0.00041)
        self.assertIsNone(usage_quote(usage, 'openai', 'unknown-model')['cost'])
        self.assertIsNone(usage_quote(None, 'openai', 'gpt-4.1-mini')['cost'])

    def test_openrouter_route_usage_and_wrong_supplier_block(self):
        os.environ.update(COUNSELOR_MODE='live', COUNSELOR_PROVIDER='openrouter',
                          OPENROUTER_API_KEY='sk-or-placeholder')
        with patch('counselor.llm.urlopen', return_value=self.response()) as call:
            llm._structured({'task': 'JSON'}, max_tokens=32)
        request = call.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, 'https://openrouter.ai/api/v1/chat/completions')
        self.assertEqual(body['model'], 'openai/gpt-4.1-mini')
        self.assertEqual(body['usage'], {'include': True})
        self.assertTrue(body['provider']['require_parameters'])
        self.assertEqual(request.get_header('Authorization'), 'Bearer sk-or-placeholder')
        os.environ.update(COUNSELOR_PROVIDER='openai', OPENAI_API_KEY='sk-or-placeholder')
        with patch('counselor.llm.urlopen') as call:
            with self.assertRaisesRegex(RuntimeError, 'OpenRouter'):
                llm._structured({'task': 'JSON'})
            call.assert_not_called()

    def test_openrouter_actual_cost_and_reserve_are_distinct(self):
        usage = {'prompt_tokens': 1000, 'completion_tokens': 100, 'cost': 0.00023}
        quote = usage_quote(usage, 'openrouter', 'openai/gpt-4.1-mini')
        self.assertEqual(quote['currency'], 'USD')
        self.assertEqual(quote['cost_basis'], 'provider_reported')
        self.assertEqual(quote['cost'], 0.00023)
        del usage['cost']
        self.assertIsNone(usage_quote(usage, 'openrouter', 'openai/gpt-4.1-mini')['cost'])
        self.assertAlmostEqual(usage_quote(usage, 'openrouter', 'openai/gpt-4.1-mini', estimate=True)['cost'], 0.00056)


if __name__ == '__main__':
    unittest.main()
