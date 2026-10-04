"""Local configuration, with process environment taking precedence over files.

Only named application settings are loaded. No shell evaluation, key copying
between providers or secret-bearing configuration representations.
"""
import os
import shlex
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_NAMES = {'COUNSELOR_MODE', 'COUNSELOR_PROVIDER', 'COUNSELOR_MODEL',
             'COUNSELOR_PORT', 'COUNSELOR_TIMEOUT', 'OPENAI_API_KEY',
             'OPENAI_BASE_URL', 'DASHSCOPE_API_KEY', 'DASHSCOPE_BASE_URL',
             'OPENROUTER_API_KEY', 'OPENROUTER_BASE_URL'}
PROVIDERS = {
    'openrouter': ('OPENROUTER_API_KEY', 'openai/gpt-4.1-mini',
                   'https://openrouter.ai/api/v1', 'OPENROUTER_BASE_URL'),
    'openai': ('OPENAI_API_KEY', 'gpt-4.1-mini', 'https://api.openai.com/v1', 'OPENAI_BASE_URL'),
    'dashscope': ('DASHSCOPE_API_KEY', 'qwen3.7-flash',
                  'https://dashscope.aliyuncs.com/compatible-mode/v1', 'DASHSCOPE_BASE_URL'),
}


def read_settings(root=None, environ=None):
    root = Path(root) if root is not None else ROOT
    values = {}
    for name in ('.env', '.env.local'):
        path = root / name
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
            line = line.strip()
            if line.startswith('export '):
                line = line[7:].strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, raw = line.split('=', 1)
            key = key.strip()
            if key not in ENV_NAMES:
                continue
            try:
                tokens = shlex.split(raw, comments=True, posix=True)
            except ValueError:
                raise RuntimeError(f'{name} 第{number}行配置引号不完整（内容已隐藏）') from None
            if len(tokens) > 1:
                raise RuntimeError(f'{name} 第{number}行配置值含未加引号的空格（内容已隐藏）')
            values[key] = tokens[0] if tokens else ''
    environment = os.environ if environ is None else environ
    values.update({key: environment[key] for key in ENV_NAMES if key in environment})
    return values


def mode():
    value = read_settings().get('COUNSELOR_MODE', 'demo').strip().lower()
    if value not in ('demo', 'live'):
        raise RuntimeError('COUNSELOR_MODE 只能是 demo 或 live')
    return value


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    model: str
    base_url: str
    key_variable: str
    api_key: str = field(repr=False)
    timeout: float = 30

    def public(self):
        return {'provider': self.provider, 'model': self.model,
                'endpoint': self.base_url + '/chat/completions',
                'key_variable': self.key_variable, 'key_present': bool(self.api_key),
                'timeout_s': self.timeout}

    def require_key(self):
        if not self.api_key:
            hint = ('；此前放在 DASHSCOPE_API_KEY 的 OpenAI 凭证需改配到 OPENAI_API_KEY'
                    if self.provider == 'openai' else '')
            raise RuntimeError(f'{self.provider} 需要 {self.key_variable}{hint}')
        if self.provider == 'dashscope' and self.api_key.startswith(('sk-proj-', 'sk-svcacct-')):
            raise RuntimeError('检测到 OpenAI 项目凭证；不能发送到 DashScope，请使用 openai 与 OPENAI_API_KEY')
        if self.provider != 'openrouter' and self.api_key.startswith('sk-or-'):
            raise RuntimeError('检测到 OpenRouter 凭证；请使用 openrouter 与 OPENROUTER_API_KEY')
        if self.provider == 'openrouter' and self.api_key.startswith(('sk-proj-', 'sk-svcacct-')):
            raise RuntimeError('OpenAI 项目凭证不能发送到 OpenRouter')
        return self


def model_config(require_key=True):
    settings = read_settings()
    provider = settings.get('COUNSELOR_PROVIDER', 'openai').strip().lower()
    if provider not in PROVIDERS:
        raise RuntimeError('COUNSELOR_PROVIDER 只能是 openai、openrouter 或 dashscope')
    key_var, default_model, default_url, url_var = PROVIDERS[provider]
    model = settings.get('COUNSELOR_MODEL', default_model).strip()
    if not model:
        raise RuntimeError('COUNSELOR_MODEL 不能为空')
    if provider == 'openrouter' and '/' not in model:
        raise RuntimeError('OpenRouter 模型必须包含供应商前缀，例如 openai/gpt-4.1-mini')
    if (provider == 'openai' and model.startswith('qwen')) or (
            provider == 'dashscope' and model.startswith(('gpt-', 'o1', 'o3', 'o4'))):
        raise RuntimeError('COUNSELOR_MODEL 与供应商不匹配，请配置对应供应商的模型')
    base_url = settings.get(url_var, default_url).strip().rstrip('/')
    allowed = {default_url}
    if provider == 'dashscope':
        allowed.add('https://dashscope-intl.aliyuncs.com/compatible-mode/v1')
    if base_url not in allowed:
        raise RuntimeError(f'{url_var} 不是当前供应商支持的官方端点')
    try:
        timeout = float(settings.get('COUNSELOR_TIMEOUT', '30'))
    except ValueError:
        raise RuntimeError('COUNSELOR_TIMEOUT 必须是1到60秒') from None
    if not 1 <= timeout <= 60:
        raise RuntimeError('COUNSELOR_TIMEOUT 必须是1到60秒')
    result = ModelConfig(provider, model, base_url, key_var,
                         settings.get(key_var, '').strip(), timeout)
    return result.require_key() if require_key else result
