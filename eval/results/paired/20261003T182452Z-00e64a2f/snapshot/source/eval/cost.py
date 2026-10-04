"""Transparent Qwen3.7-Flash cost calculations for the Beijing endpoint.

Rates are a dated snapshot, not a bill. Live runs should use API usage fields.
"""

from dataclasses import dataclass

SOURCE_URL = "https://help.aliyun.com/zh/model-studio/qwen3-7-flash"
PRICE_CHECKED_ON = "2026-10-03"
MODEL = "qwen3.7-flash"
REGION = "华北2（北京）"
# RMB per million tokens, regular non-cached synchronous calls.
TIERS = ((32_000, 0.2, 0.8), (256_000, 0.6, 2.4), (1_000_000, 1.2, 4.8))


@dataclass(frozen=True)
class CallEstimate:
    name: str
    count: int
    input_tokens_each: int
    output_tokens_each: int


def cost_rmb(input_tokens, output_tokens):
    """Per-request input length selects the official pricing tier."""
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int) \
            or input_tokens < 0 or output_tokens < 0:
        raise ValueError("token usage must be non-negative integers")
    for limit, input_rate, output_rate in TIERS:
        if input_tokens <= limit:
            return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
    raise ValueError("input exceeds the model's published pricing tiers")


def usage_cost(usage):
    """Return cost only when the provider supplied both token counts."""
    if not isinstance(usage, dict):
        return None
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
        return None
    return cost_rmb(input_tokens, output_tokens)


def usage_quote(usage, provider, model):
    """Currency-aware live estimate; unknown models never inherit Qwen prices."""
    quote = {'cost': None, 'currency': 'USD' if provider == 'openai' else 'CNY',
             'price_source': None, 'price_checked_on': None}
    if provider == 'dashscope' and model == MODEL:
        quote.update(cost=usage_cost(usage), price_source=SOURCE_URL,
                     price_checked_on=PRICE_CHECKED_ON)
    elif provider == 'openai' and model in ('gpt-4.1-mini', 'gpt-4.1-mini-2025-04-14'):
        quote.update(price_source='https://developers.openai.com/api/docs/models/gpt-4.1-mini',
                     price_checked_on='2026-10-04')
        if isinstance(usage, dict):
            inp = usage.get('prompt_tokens', usage.get('input_tokens'))
            out = usage.get('completion_tokens', usage.get('output_tokens'))
            details = usage.get('prompt_tokens_details') or usage.get('input_tokens_details') or {}
            cached = details.get('cached_tokens', 0) if isinstance(details, dict) else None
            if all(type(n) is int and n >= 0 for n in (inp, out, cached)) and cached <= inp:
                quote['cost'] = ((inp-cached)*0.4 + cached*0.1 + out*1.6)/1_000_000
    return quote


SCENARIOS = {
    "structured_cv_one_answer_no_rewrite": [
        CallEstimate("answer_parse", 1, 400, 150),
        CallEstimate("brief_generation", 1, 3000, 1200),
        CallEstimate("claim_review", 1, 2500, 900),
    ],
    "structured_cv_eight_answers_with_rewrite": [
        CallEstimate("answer_parse", 8, 400, 150),
        CallEstimate("brief_generation", 1, 3000, 1200),
        CallEstimate("claim_review", 1, 2500, 900),
        CallEstimate("narrowed_claim_recheck", 1, 2000, 700),
    ],
}


def scenario_totals(calls):
    return {
        "requests": sum(c.count for c in calls),
        "assumed_input_tokens": sum(c.count * c.input_tokens_each for c in calls),
        "assumed_output_tokens": sum(c.count * c.output_tokens_each for c in calls),
        "estimated_rmb": round(sum(
            c.count * cost_rmb(c.input_tokens_each, c.output_tokens_each)
            for c in calls), 6),
    }


if __name__ == "__main__":
    import json
    print(json.dumps({name: scenario_totals(calls) for name, calls in SCENARIOS.items()},
                     ensure_ascii=False, indent=2))
