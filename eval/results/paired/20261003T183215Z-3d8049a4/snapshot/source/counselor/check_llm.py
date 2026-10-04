"""Safe configuration inspection; --live makes one small JSON generation call."""
import argparse
import json
import os
from .config import model_config, mode
from .llm import _structured


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='执行一次最小实际模型请求')
    args = parser.parse_args()
    try:
        config = model_config(require_key=False)
        result = {'mode': mode(), **config.public(), 'live_test': args.live}
        if args.live:
            config.require_key()
            os.environ['COUNSELOR_MODE'] = 'live'
            answer, usage = _structured({'task': '只返回 JSON 对象 {"ok": true}。'}, max_tokens=32)
            if answer.get('ok') is not True:
                raise RuntimeError('模型响应收到，但最小 JSON 内容校验失败')
            result.update({'status': 'ok', 'usage': usage})
        else:
            result['status'] = 'configuration_only_not_connection_verified'
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except RuntimeError as exc:
        print(json.dumps({'status': 'failed', 'error': str(exc)}, ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
