"""Aggregate finalized atomic/gap/opportunity judgements; never auto-infer truth."""
import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from statistics import mean

from eval.paired_eval import ARMS, save, digest


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as file:
        return list(csv.DictReader(file))


def aggregate(pack, mapping, gold, judgements):
    entries = {e['blind_id']: e for e in pack}
    if len(entries) != len(pack) or set(entries) != set(mapping):
        raise ValueError('匿名包与映射不匹配')
    grouped = {name: {} for name in ('claims', 'gaps', 'opportunities', 'cases')}
    for name, rows in judgements.items():
        if name not in grouped:
            continue
        for row in rows:
            bid = row['blind_id']
            if bid not in entries or row['case_id'] != entries[bid]['case_id']:
                raise ValueError('评分包含未知匿名ID或案例不匹配')
            grouped[name].setdefault(bid, []).append(row)
    per_case = []
    for bid, entry in entries.items():
        cid, arm = entry['case_id'], mapping[bid]['arm']
        if arm not in ARMS or mapping[bid]['case_id'] != cid:
            raise ValueError('组别映射不合法')
        delivered = entry['delivered']
        case_rows = grouped['cases'].get(bid, [])
        if len(case_rows) != 1 or case_rows[0]['delivered'] != str(int(delivered)):
            raise ValueError(f'{bid}:案例交付状态缺失、重复或与原始输出冲突')
        case_row = case_rows[0]
        claim_rows = grouped['claims'].get(bid, [])
        labels, texts, ids = Counter(), set(), set()
        for row in claim_rows:
            if not delivered:
                raise ValueError('未交付案例不能填已发布论点')
            label = row['label']
            if label not in ('supported', 'overstated', 'insufficient', 'contradicted'):
                raise ValueError('存在未裁决的论点标签')
            if not row['claim_id'] or not row['claim_text'].strip() or not row['reason'].strip():
                raise ValueError('论点编号、内容或判定理由缺失')
            if row['claim_id'] in ids or row['claim_text'].strip() in texts:
                raise ValueError('论点重复或尚未合并两人原判；请先保存裁决后的共同单元')
            ids.add(row['claim_id'])
            texts.add(row['claim_text'].strip())
            labels[label] += 1
        if delivered and case_row['no_usable_claims'] not in ('0', '1'):
            raise ValueError('成功交付案例尚未填写空输出/拒答判断')
        if delivered and not claim_rows and case_row['no_usable_claims'] != '1':
            raise ValueError('零论点案例不能标为有可用论点')

        def scored_units(name, key, include_key):
            expected = {x[key]: x for x in gold[cid][name] if x[include_key] == 1}
            rows = grouped[name].get(bid, [])
            by_id = {r[key]: r for r in rows}
            if len(by_id) != len(rows) or set(by_id) != set(expected):
                raise ValueError(f'{bid}:{name}缺项、重复或引用未知gold')
            hits, primary_hits, primary_total = 0, 0, 0
            for uid, reference in expected.items():
                row = by_id[uid]
                if delivered:
                    if name == 'gaps':
                        if row['label'] not in ('detected', 'partial', 'missed', 'wrong'):
                            raise ValueError('存在未裁决的缺口标签')
                        hit = row['label'] == 'detected'
                    else:
                        if row['retained'] not in ('0', '1'):
                            raise ValueError('有用机会保留判断未填完')
                        hit = row['retained'] == '1'
                    if hit and not row['output_locator'].strip():
                        raise ValueError('命中缺口/事实机会必须给出输出位置')
                    if not row['reason'].strip():
                        raise ValueError('缺口/保留判定必须给出理由')
                else:
                    # Delivery metrics: missing output has no hits, without
                    # inventing semantic judgements for an absent document.
                    hit = False
                hits += int(hit)
                if reference['experience_id'] == 'exp_1':
                    primary_total += 1
                    primary_hits += int(hit)
            return hits, len(expected), primary_hits, primary_total

        gap_hit, gap_total, _, _ = scored_units('gaps', 'gap_id', 'include_primary')
        opp_hit, opp_total, primary_hit, primary_total = scored_units('opportunities', 'opportunity_id', 'include_retention')
        published = sum(labels.values())
        unsafe = published-labels['supported']
        if not published and opp_hit:
            raise ValueError('保留了有用事实却没有任何已发布论点标注，请完成拆分')
        per_case.append({'blind_id': bid, 'case_id': cid, 'arm': arm, 'delivered': delivered,
                         'published_claims': published, 'unsupported_claims': unsafe,
                         'unsupported_claim_rate': ratio(unsafe, published),
                         'gap_hits': gap_hit, 'gap_total': gap_total,
                         'gap_coverage': ratio(gap_hit, gap_total),
                         'opportunity_hits': opp_hit, 'opportunity_total': opp_total,
                         'primary_opportunity_hits': primary_hit, 'primary_opportunity_total': primary_total,
                         'no_usable_claims': not delivered or case_row['no_usable_claims'] == '1',
                         'claim_label_counts': dict(labels)})
    summaries = {}
    for arm in ARMS:
        rows = [r for r in per_case if r['arm'] == arm]
        claims = sum(r['published_claims'] for r in rows)
        unsafe = sum(r['unsupported_claims'] for r in rows)
        gaps = sum(r['gap_total'] for r in rows)
        gap_hits = sum(r['gap_hits'] for r in rows)
        opportunities = sum(r['opportunity_total'] for r in rows)
        opp_hits = sum(r['opportunity_hits'] for r in rows)
        main_total = sum(r['primary_opportunity_total'] for r in rows)
        main_hits = sum(r['primary_opportunity_hits'] for r in rows)
        ratios = [r['unsupported_claim_rate'] for r in rows if r['unsupported_claim_rate'] is not None]
        successful = [r for r in rows if r['delivered']]
        summaries[arm] = {'cases': len(rows), 'delivered': len(successful),
            'unsupported_claims': unsafe, 'published_claims': claims,
            'unsupported_claim_rate': ratio(unsafe, claims),
            'unsupported_claim_rate_macro': mean(ratios) if ratios else None,
            'claim_rate_na_cases': sum(r['unsupported_claim_rate'] is None for r in rows),
            'gap_hits': gap_hits, 'gap_total': gaps, 'gap_coverage': ratio(gap_hits, gaps),
            'opportunity_hits': opp_hits, 'opportunity_total': opportunities,
            'retention': ratio(opp_hits, opportunities),
            'primary_retention': ratio(main_hits, main_total),
            'secondary_retention': ratio(opp_hits-main_hits, opportunities-main_total),
            'failure_rate': ratio(len(rows)-len(successful), len(rows)),
            'empty_or_abstention_rate': ratio(sum(r['no_usable_claims'] for r in rows), len(rows)),
            'successful_delivery_gap_coverage': ratio(sum(r['gap_hits'] for r in successful), sum(r['gap_total'] for r in successful)),
            'claim_target_met': ratio(unsafe, claims) < 0.1 if claims else None}
    return {'arms': summaries, 'per_case': per_case,
            'note': 'AI-authored synthetic references; reported judgements require rater provenance. No independent-held-out claim.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run_directory', type=Path)
    parser.add_argument('--judgements', type=Path, help='裁决后的评分目录；默认run/judgements')
    parser.add_argument('--rater', required=True, help='评分者或裁决者身份；AI须明确注明')
    args = parser.parse_args()
    run = args.run_directory
    manifest = json.loads((run/'run_manifest.json').read_text())
    if (run/'scored_metrics.json').exists():
        raise SystemExit('已有评分汇总，不能覆盖首次评分；修订须另存版本')
    if manifest['dry_run']:
        raise SystemExit('离线夹具不能计算真实模型质量指标')
    for name, expected in json.loads((run/'artifacts_sha256.json').read_text())['files'].items():
        if digest(run/name) != expected:
            raise SystemExit(f'原始运行产物已变化：{name}')
    pack = [json.loads(line) for line in (run/'blind_pack.jsonl').read_text().splitlines()]
    mapping = json.loads((run/'private'/'blind_mapping.json').read_text())
    gold = {cid: json.loads((run/'snapshot'/cid/'stage_gold.json').read_text()) for cid in manifest['case_ids']}
    folder = args.judgements or run/'judgements'
    judgements = {n: read_csv(folder/f'{n}.csv') for n in ('claims', 'gaps', 'opportunities', 'cases')}
    try:
        summary = aggregate(pack, mapping, gold, judgements)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    slices = {cid: json.loads((run/'cases'/cid/'run.json').read_text())['slice'] for cid in manifest['case_ids']}
    summary['slice_counts'] = {}
    for arm in ARMS:
        for risk in sorted(set(slices.values())):
            rows = [r for r in summary['per_case'] if r['arm'] == arm and slices[r['case_id']] == risk]
            summary['slice_counts'][f'{arm}:{risk}'] = {key: sum(r[key] for r in rows)
                for key in ('published_claims', 'unsupported_claims', 'gap_hits', 'gap_total', 'opportunity_hits', 'opportunity_total')}
    summary['rater_or_adjudicator'] = args.rater
    summary['judgement_file_hashes'] = {n: digest(folder/f'{n}.csv') for n in judgements}
    summary['cost'] = json.loads((run/'summary.json').read_text())['cost']
    save(run/'scored_metrics.json', summary)
    print(json.dumps(summary['arms'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
