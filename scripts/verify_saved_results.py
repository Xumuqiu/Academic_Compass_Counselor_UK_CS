"""Read-only verification of frozen artifacts and saved annotation aggregates.

No model requests, new labels or writes are made. Semantic judgements are reused,
not independently reviewed. Run from the project root with python -m scripts.verify_saved_results.
"""
import hashlib
import json
from pathlib import Path
from eval.score_paired import aggregate, read_csv

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / 'eval/results/paired/20261003T183705Z-8d15689b'


def verify_file(path, expected):
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('Hash mismatch: ' + str(path.relative_to(ROOT)))


def main():
    manifest = json.loads((RUN / 'run_manifest.json').read_text(encoding='utf-8'))
    if manifest['dry_run']:
        raise ValueError('Expected a real-model run, not fixtures.')
    files = json.loads((RUN / 'artifacts_sha256.json').read_text(encoding='utf-8'))['files']
    for name, expected in files.items():
        verify_file(RUN / name, expected)
    saved = json.loads((RUN / 'scored_metrics.json').read_text(encoding='utf-8'))
    folder = RUN / 'judgements/final_v1'
    for name, expected in saved['judgement_file_hashes'].items():
        verify_file(folder / (name + '.csv'), expected)
    judgements = {name: read_csv(folder / (name + '.csv'))
                  for name in ('claims', 'gaps', 'opportunities', 'cases')}
    pack = [json.loads(line) for line in (RUN / 'blind_pack.jsonl').read_text(encoding='utf-8').splitlines()]
    mapping = json.loads((RUN / 'private/blind_mapping.json').read_text(encoding='utf-8'))
    gold = {cid: json.loads((RUN / 'snapshot' / cid / 'stage_gold.json').read_text(encoding='utf-8'))
            for cid in manifest['case_ids']}
    actual = aggregate(pack, mapping, gold, judgements)
    if actual['arms'] != saved['arms'] or actual['per_case'] != saved['per_case']:
        raise ValueError('Recalculated metrics differ from saved metrics.')
    print('PASS: {} frozen artifacts and all four judgement CSV hashes verified.'.format(len(files)))
    print('PASS: group and per-case aggregates match the saved results.')
    print(json.dumps(actual['arms'], ensure_ascii=False, indent=2))
    print('No API calls or file changes. These are single-AI-rater synthetic results, not independent validation.')


if __name__ == '__main__':
    main()
