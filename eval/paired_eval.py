"""Controlled CV-to-brief comparison, with isolated fixtures and immutable runs.

--dry-run verifies the machinery with explicit fixtures, not model quality.
--live replays frozen actual turns, shares parsing and generation, then reviews
only the full_guardrail arm. Gold is never passed to either model call.
"""
import argparse
import csv
import hashlib
import json
import os
import random
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from counselor import llm
from counselor.claim_check import checked_proposals, propose_narrowings
from counselor.config import model_config
from counselor.data import list_programmes
from counselor.document import export_docx
from counselor.intake import normalize_cv
from counselor.workflow import start_case, answer_question, make_result
from eval.cost import usage_quote

BASE = Path(__file__).resolve().parent
DATA = BASE / 'data' / 'synthetic_profiles_v1'
GOLD = BASE / 'annotations' / 'stage_gold_v1'
ARMS = ('prompt_only', 'full_guardrail')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify_snapshot(root):
    for name, expected in json.loads((root/'checksums.json').read_text())['files'].items():
        if digest(root/name) != expected:
            raise RuntimeError(f'快照变化：{name}；请生成并审核新版本')


def load_profiles(split, limit=None):
    verify_snapshot(DATA)
    verify_snapshot(GOLD)
    annotation = json.loads((GOLD/'manifest.json').read_text())
    if annotation['scoring_rules_sha256'] != digest(BASE/'SCORING_RULES.md'):
        raise RuntimeError('评分规则已变化，需要复核标注版本')
    if annotation['original_data_checksums_sha256'] != digest(DATA/'checksums.json'):
        raise RuntimeError('标注与数据版本不匹配')
    profiles = [p for p in json.loads((DATA/'manifest.json').read_text())['profiles']
                if p['split'] == split]
    if limit is not None:
        if limit < 1:
            raise ValueError('limit必须大于0')
        profiles = profiles[:limit]
    return profiles


def prompt_only_result(state, proposal):
    """Eval-only publication; never spoof the production guard-pass marker.

Both arms use the product's current core projection (angles and thesis).
Free model guide/positioning/section prose is discarded by the guarded product,
so it is also discarded here; otherwise the comparison changes two things.
"""
    result = make_result(state)
    by_id = {m['experience_id']: m for m in result['materials']}
    for item in proposal.get('materials', []):
        target = by_id.get(item.get('experience_id'))
        if target is not None:
            target['angle'] = item['angle']
            target['evidence_quote'] = item.get('evidence_quote')
            target['guide_note'] = (f"适合围绕{item['angle']}与学生继续核实。"
                                   '写作时只使用上方已记录的事实；空缺项留待追问。')
    result['thesis_claim'] = proposal['thesis_claim']
    result['mode'] = 'prompt_only_eval'
    return result


def validate_proposal(state, proposal):
    if not isinstance(proposal, dict) or not isinstance(proposal.get('materials'), list):
        raise RuntimeError('候选素材包缺少materials列表')
    if not isinstance(proposal.get('thesis_claim'), str) or not proposal['thesis_claim'].strip():
        raise RuntimeError('候选素材包缺少主线')
    expected = {r['experience_id'] for r in state['records']}
    ids = []
    for item in proposal['materials']:
        if (not isinstance(item, dict) or not isinstance(item.get('angle'), str)
                or not item['angle'].strip()):
            raise RuntimeError('候选素材包的角度格式不合法')
        ids.append(item.get('experience_id'))
    if len(ids) != len(expected) or set(ids) != expected:
        raise RuntimeError('候选素材包经历ID缺失、重复或未知')


class FixtureBackend:
    """Authored mock responses for pipeline verification only."""
    def generate(self, state):
        materials = []
        for record in state['records']:
            fact = next(f for f in record['fact_items'] if f['confirmation'] == 'student_stated')
            materials.append({'experience_id': record['experience_id'],
                              'angle': fact['text'], 'evidence_quote': fact['text']})
        return {'thesis_claim': materials[0]['angle'],
                'thesis_evidence_quote': materials[0]['evidence_quote'], 'materials': materials}, None

    def review(self, state, proposal):
        results = []
        for kind, eid, claim in [('angle', m['experience_id'], m['angle']) for m in proposal.get('materials', [])] + (
                [('thesis', None, proposal['thesis_claim'])] if proposal.get('thesis_claim') else []):
            fact = next((f for r in state['records'] for f in r['fact_items']
                         if (eid is None or eid == r['experience_id'])
                         and f['confirmation'] == 'student_stated' and claim == f['text']), None)
            results.append({'kind': kind, 'experience_id': eid, 'claim': claim,
                            'segments': [{'text': claim, 'verdict': 'supported' if fact else 'insufficient',
                                          'evidence': [{'fact_id': fact['id'], 'quote': fact['text']}] if fact else [],
                                          'reason': '离线夹具，不是模型判断'}]})
        return {'claims': results}, None


class Meter:
    def __init__(self, config, dry_run, budget):
        self.config, self.dry_run, self.budget = config, dry_run, budget
        self.calls = []
        self.case_id, self.arm, self.stage = None, 'shared', None
        self.known_cost = 0
        self.unknown_cost = False
        self.log_path = None

    @contextmanager
    def stage_context(self, arm, stage):
        previous = self.arm, self.stage
        self.arm, self.stage = arm, stage
        try:
            yield
        finally:
            self.arm, self.stage = previous

    @contextmanager
    def install(self):
        original = llm._structured

        def measured(prompt, max_tokens=1800):
            if self.dry_run:
                raise RuntimeError('离线运行不能调用模型')
            if self.unknown_cost:
                raise RuntimeError('上一调用费用未知，停止新请求并保留失败记录')
            # Byte count deliberately overestimates tokens; ignore cache savings.
            input_bound = 2*len(json.dumps(prompt, ensure_ascii=False).encode()) + 4096
            reserve = usage_quote({'prompt_tokens': input_bound, 'completion_tokens': max_tokens},
                                  self.config.provider, self.config.model, estimate=True)['cost']
            if reserve is None or self.known_cost + reserve > self.budget:
                raise RuntimeError('当前价格未知或保守费用预留超过预算，停止新请求')
            started = perf_counter()
            row = {'call_id': f'call_{len(self.calls)+1}', 'case_id': self.case_id,
                   'arm': self.arm, 'stage': self.stage, 'provider': self.config.provider,
                   'model': self.config.model, 'actual_model_call': True,
                   'status': 'failed', 'usage': None, 'cost': None,
                   'currency': usage_quote(None, self.config.provider, self.config.model)['currency'],
                   'retry_of': None, 'prompt': deepcopy(prompt), 'max_tokens': max_tokens}
            try:
                result, usage = original(prompt, max_tokens=max_tokens)
                row.update(status='ok', usage=usage,
                           **usage_quote(usage, self.config.provider, self.config.model))
                row['response'] = deepcopy(result)
                return result, usage
            except RuntimeError as exc:
                row['error'] = str(exc)  # Shared outlet exposes only safe errors.
                raise
            finally:
                row['latency_s'] = round(perf_counter()-started, 4)
                self.calls.append(row)
                if self.log_path is not None:
                    with self.log_path.open('a', encoding='utf-8') as file:
                        file.write(json.dumps(row, ensure_ascii=False)+'\n')
                if row['cost'] is None:
                    self.unknown_cost = True
                else:
                    self.known_cost += row['cost']

        llm._structured = measured
        try:
            yield self
        finally:
            llm._structured = original


def cost_summary(calls, dry_run):
    def total(items):
        return sum(c['cost'] for c in items) if all(c['cost'] is not None for c in items) else None
    shared = total([c for c in calls if c['arm'] == 'shared'])
    guard = total([c for c in calls if c['arm'] == 'full_guardrail'])
    return {'currency': calls[0]['currency'] if calls else None,
            'shared_upstream_cost': shared, 'guard_increment_cost': guard,
            'standalone_prompt_only_cost': shared,
            'standalone_full_guardrail_cost': shared+guard if shared is not None and guard is not None else None,
            'actual_experiment_estimated_cost': total(calls),
            'actual_experiment_cost': total(calls),
            'cost_basis': 'provider_reported' if calls and all(c.get('cost_basis') == 'provider_reported' for c in calls) else 'usage_based_estimate_or_unknown',
            'unknown_cost_calls': sum(c['cost'] is None for c in calls),
            'actual_model_requests': len(calls), 'dry_run': dry_run,
            'cost_is_usage_based_estimate_not_provider_bill': not (calls and all(c.get('cost_basis') == 'provider_reported' for c in calls))}


def run_profile(profile, meter, dry_run=False):
    folder = DATA/profile['split']/profile['case_id']
    cv = normalize_cv(json.loads((folder/'cv.json').read_text()))
    frozen = json.loads((folder/'simulated_transcript.json').read_text())
    programmes = [p for p in list_programmes() if p['id'] in profile['program_ids']]
    state = start_case(cv, programmes)
    row = {'case_id': profile['case_id'], 'slice': profile['slice'],
           'dry_run': dry_run, 'actual_transcript': [], 'outputs': {}, 'failures': {},
           'failure_stage': None, 'proposal': None, 'reviews': {}, 'programmes': deepcopy(programmes)}
    meter.case_id = profile['case_id']
    first_call = len(meter.calls)
    fixture = FixtureBackend()
    stage = 'answer_parse'
    try:
        for turn in frozen['turns']:
            # The model parser may enrich state, but must not change fixed inputs.
            q = {'id': turn['question_id'], 'experience_id': turn['experience_id'],
                 'element': turn['element'], 'text': turn['question']}
            row['actual_transcript'].append(deepcopy(turn))
            with meter.stage_context('shared', 'answer_parse'):
                state = answer_question(state, turn['answer'],
                    parse=None if dry_run else llm.parse_experience_answer,
                    recorded_question=q)
        stage = 'brief_generation'
        with meter.stage_context('shared', stage):
            proposal, _ = fixture.generate(state) if dry_run else llm.generate_full_brief(state)
        row['proposal'] = proposal
        row['state'] = state
        validate_proposal(state, proposal)
        stage = 'prompt_only_export'
        baseline = prompt_only_result(state, proposal)
        export_docx(baseline)  # Failed export is a delivery failure, not a pass.
        row['outputs']['prompt_only'] = baseline
        stage = 'claim_review'
        with meter.stage_context('full_guardrail', stage):
            first, _ = fixture.review(state, proposal) if dry_run else llm.review_full_brief_claims(state, proposal)
        row['reviews']['first'] = first
        narrowed = propose_narrowings(proposal, first)
        second = None
        if narrowed.get('materials') or narrowed.get('thesis_claim'):
            stage = 'narrowed_claim_recheck'
            try:
                with meter.stage_context('full_guardrail', stage):
                    second, _ = fixture.review(state, narrowed) if dry_run else llm.review_full_brief_claims(state, narrowed)
            except RuntimeError as exc:
                row['recheck_warning'] = str(exc)
                # Match the product: failed narrowing remains unpublished,
                # while independently supported original claims can remain.
            row['reviews']['second'] = second
        stage = 'full_guardrail_export'
        checked, questions = checked_proposals(state, proposal, first, second)
        result = make_result(state, checked)
        result['open_questions'].extend(questions)
        export_docx(result)
        row['outputs']['full_guardrail'] = result
    except (RuntimeError, ValueError, TypeError, KeyError) as exc:
        row['failure_stage'] = stage
        for arm in ARMS:
            if arm not in row['outputs']:
                row['failures'][arm] = {'stage': stage, 'error': f'{type(exc).__name__}: {str(exc)[:240]}'}
    row['calls'] = deepcopy(meter.calls[first_call:])
    row['cost_summary'] = cost_summary(row['calls'], dry_run)
    if dry_run:
        for result in row['outputs'].values():
            result['notice'] = '离线夹具流程验证：不是实际模型输出，不可计入质量评分。'
            result['mode'] = 'verification_fixture'
    return row


def write_pack(run_dir, rows, seed, dry_run):
    mapping, pack = {}, []
    for row in rows:
        folder = run_dir/'cases'/row['case_id']
        save(folder/'run.json', row)
        for arm in ARMS:
            blind_id = uuid.uuid4().hex[:16]
            mapping[blind_id] = {'case_id': row['case_id'], 'arm': arm}
            output = row['outputs'].get(arm)
            if output is not None:
                (folder/f'{arm}.docx').write_bytes(export_docx(output))
            public = {k: v for k, v in (output or {}).items() if k not in ('mode', 'claim_audit')}
            pack.append({'blind_id': blind_id, 'case_id': row['case_id'],
                         'verification_fixture': dry_run, 'delivered': output is not None,
                         'input': {'cv': json.loads((run_dir/'snapshot'/row['case_id']/'cv.json').read_text()),
                                   'actual_transcript': row['actual_transcript'], 'programmes': row['programmes']},
                         'result': public if output is not None else None,
                         'failure_stage': row['failures'].get(arm, {}).get('stage')})
    random.Random(seed).shuffle(pack)
    save(run_dir/'private'/'blind_mapping.json', mapping)
    (run_dir/'blind_pack.jsonl').write_text(''.join(json.dumps(p, ensure_ascii=False)+'\n' for p in pack))
    score_dir = run_dir/'judgements'
    score_dir.mkdir()
    for name in ('claims', 'gaps', 'opportunities', 'cases', 'adjudications'):
        with (BASE/'scoring_templates'/f'{name}.csv').open(newline='') as f:
            header = next(csv.reader(f))
        with (score_dir/f'{name}.csv').open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            for entry in pack:
                gold = json.loads((GOLD/f"{entry['case_id']}.json").read_text())
                if name == 'cases':
                    writer.writerow({'blind_id': entry['blind_id'], 'case_id': entry['case_id'],
                                     'delivered': int(entry['delivered']),
                                     'failure_stage': entry['failure_stage'] or ''})
                elif name in ('gaps', 'opportunities'):
                    key = 'gap_id' if name == 'gaps' else 'opportunity_id'
                    for item in gold[name]:
                        writer.writerow({'blind_id': entry['blind_id'], 'case_id': entry['case_id'], key: item[key]})
    calls = [call for row in rows for call in row['calls']]
    (run_dir/'calls.jsonl').write_text(''.join(json.dumps(c, ensure_ascii=False)+'\n' for c in calls))
    for name in ('calls', 'cost_summary'):
        with (BASE/'scoring_templates'/f'{name}.csv').open(newline='') as file:
            header = next(csv.reader(file))
        with (run_dir/f'{name}.csv').open('w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=header, extrasaction='ignore')
            writer.writeheader()
            if name == 'calls':
                for call in calls:
                    usage = call.get('usage') or {}
                    writer.writerow({**call, 'run_id': run_dir.name,
                        'input_tokens': usage.get('prompt_tokens', usage.get('input_tokens')),
                        'output_tokens': usage.get('completion_tokens', usage.get('output_tokens')),
                        'cached_input_tokens': (usage.get('prompt_tokens_details') or {}).get('cached_tokens'),
                        'cost_status': 'known_estimate' if call['cost'] is not None else 'unknown'})
            else:
                for row in rows:
                    cost = row['cost_summary']
                    for arm in ARMS:
                        writer.writerow({'run_id': run_dir.name, 'case_id': row['case_id'], 'arm': arm,
                            'currency': cost['currency'], 'shared_upstream_cost': cost['shared_upstream_cost'],
                            'guard_increment_cost': cost['guard_increment_cost'] if arm == 'full_guardrail' else 0,
                            'retry_cost': 0, 'standalone_deployment_cost': cost[f'standalone_{arm}_cost'],
                            'actual_experiment_allocated_cost': cost['shared_upstream_cost'] if arm == 'prompt_only' else cost['guard_increment_cost'],
                            'delivered': int(arm in row['outputs']), 'unknown_cost_calls': cost['unknown_cost_calls'],
                            'notes': '离线夹具，无API调用' if dry_run else '共享上游仅支付一次；价格估算不是供应商账单'})


def run(split='dev', dry_run=True, limit=None, budget=10.0, output_root=None, pilot_run=None):
    profiles = load_profiles(split, limit)
    config = model_config(require_key=not dry_run)
    pricing = usage_quote(None, config.provider, config.model)
    if config.provider == 'dashscope' and config.base_url != 'https://dashscope.aliyuncs.com/compatible-mode/v1':
        pricing.update(cost=None, price_source=None, price_checked_on=None)
    if not dry_run and (budget <= 0 or pricing['price_source'] is None):
        raise RuntimeError('真实运行须设置正预算并使用已支持计价的模型')
    if not dry_run and split == 'evaluation_candidates':
        if len(profiles) != 20 or pilot_run is None:
            raise RuntimeError('20例候选真实运行须提供已成功的6例开发预跑 --pilot-run')
        pilot = Path(pilot_run)
        pm = json.loads((pilot/'run_manifest.json').read_text())
        ps = json.loads((pilot/'summary.json').read_text())
        if (pm['dry_run'] or pm['split'] != 'dev' or pm['planned_sample_count'] != 6
                or any(ps['delivered_by_arm'][arm] != 6 for arm in ARMS)
                or pm['provider'] != config.provider or pm['model'] != config.model
                or pm['data_checksums_sha256'] != digest(DATA/'checksums.json')
                or pm['stage_gold_checksums_sha256'] != digest(GOLD/'checksums.json')
                or pm['scoring_rules_sha256'] != digest(BASE/'SCORING_RULES.md')
                or any(digest(BASE.parent/name) != value for name, value in pm['code_hashes'].items())
                or any(digest(BASE.parent/name) != value for name, value in pm['reference_data_hashes'].items())):
            raise RuntimeError('开发预跑未成功或版本/配置不同，不能作为20例运行准备证据')
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run_dir = Path(output_root or BASE/'results'/'paired')/run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    snapshots = run_dir/'snapshot'
    for profile in profiles:
        cid = profile['case_id']
        folder = DATA/profile['split']/cid
        for name in ('cv.json', 'simulated_transcript.json'):
            save(snapshots/cid/name, json.loads((folder/name).read_text()))
        save(snapshots/cid/'stage_gold.json', json.loads((GOLD/f'{cid}.json').read_text()))
    code = list((BASE.parent/'counselor').glob('*.py')) + list(BASE.glob('*.py'))
    reference_data = list((BASE.parent/'data').glob('*.json'))
    for path in code + reference_data + [BASE/'SCORING_RULES.md']:
        target = snapshots/'source'/path.relative_to(BASE.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    manifest = {'run_id': run_id, 'status': 'verification_fixture' if dry_run else 'frozen_before_first_call',
                'dry_run': dry_run, 'split': split, 'case_ids': [p['case_id'] for p in profiles],
                'planned_sample_count': len(profiles), 'provider': config.provider, 'model': config.model,
                'endpoint': config.base_url, 'pricing': pricing, 'budget_limit': budget,
                'budget_currency': pricing['currency'], 'independent_held_out_count': 0,
                'gold_author_review': 'AI author; no independent human review',
                'data_checksums_sha256': digest(DATA/'checksums.json'),
                'stage_gold_checksums_sha256': digest(GOLD/'checksums.json'),
                'scoring_rules_sha256': digest(BASE/'SCORING_RULES.md'),
                'prompt_source_sha256': digest(BASE.parent/'counselor'/'llm.py'),
                'code_hashes': {p.relative_to(BASE.parent).as_posix(): digest(p) for p in code},
                'reference_data_hashes': {p.relative_to(BASE.parent).as_posix(): digest(p) for p in reference_data},
                'generation_parameters': {'temperature': 0, 'response_format': 'json_object', 'max_tokens': 4000},
                'protocol': 'fixed_recorded_turns_shared_parsing_shared_candidate_core_projection',
                'discarded_candidate_fields_both_arms': ['guide_note', 'translated_positioning', 'sections'],
                'retry_policy': 'no_automatic_retries; first attempt retained',
                'pilot_run_directory': str(pilot_run) if pilot_run else None,
                'frozen_at_utc': datetime.now(timezone.utc).isoformat()}
    save(run_dir/'run_manifest.json', manifest)
    meter = Meter(config, dry_run, budget)
    meter.log_path = run_dir/'calls.jsonl'
    prior_mode = os.environ.get('COUNSELOR_MODE')
    if not dry_run:
        os.environ['COUNSELOR_MODE'] = 'live'
    rows = []
    try:
        with meter.install():
            for profile in profiles:
                row = run_profile(profile, meter, dry_run)
                rows.append(row)
                save(run_dir/'cases'/profile['case_id']/'run.json', row)
    finally:
        if prior_mode is None:
            os.environ.pop('COUNSELOR_MODE', None)
        else:
            os.environ['COUNSELOR_MODE'] = prior_mode
    write_pack(run_dir, rows, seed=20261004, dry_run=dry_run)
    summary = {'run_id': run_id, 'dry_run': dry_run, 'cases_attempted': len(rows),
               'delivered_by_arm': {arm: sum(arm in r['outputs'] for r in rows) for arm in ARMS},
               'quality_metrics': 'not_scored; requires actual output annotations',
               'cost': cost_summary(meter.calls, dry_run),
               'failures': {r['case_id']: r['failures'] for r in rows if r['failures']}}
    summary['cost']['currency'] = pricing['currency']
    summary['cost']['per_successful_delivery_standalone_cost'] = {}
    for arm in ARMS:
        costs = [r['cost_summary'][f'standalone_{arm}_cost'] for r in rows]
        successes = summary['delivered_by_arm'][arm]
        summary['cost']['per_successful_delivery_standalone_cost'][arm] = (
            sum(costs)/successes if successes and all(c is not None for c in costs) else None)
    save(run_dir/'summary.json', summary)
    manifest['status'] = 'verification_complete' if dry_run else 'first_attempt_complete'
    save(run_dir/'run_manifest.json', manifest)
    save(run_dir/'artifacts_sha256.json', {'files': {
        p.relative_to(run_dir).as_posix(): digest(p) for p in sorted(run_dir.rglob('*'))
        if p.is_file() and 'judgements' not in p.relative_to(run_dir).parts
        and p.name != 'artifacts_sha256.json'}})
    print(json.dumps({'run_directory': str(run_dir), **summary}, ensure_ascii=False, indent=2))
    return run_dir


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--dry-run', action='store_true')
    group.add_argument('--live', action='store_true')
    parser.add_argument('--split', choices=('dev', 'evaluation_candidates'), default='dev')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--budget', type=float, default=10.0, help='预算单位为供应商计价币种')
    parser.add_argument('--pilot-run', type=Path)
    args = parser.parse_args()
    try:
        run(args.split, args.dry_run, args.limit, args.budget, pilot_run=args.pilot_run)
    except (RuntimeError, ValueError) as exc:
        raise SystemExit(str(exc)) from None


if __name__ == '__main__':
    main()
