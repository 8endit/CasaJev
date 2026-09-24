"""Frozen sequential CSV workflow comparison; synthetic data only.

Run with an empty output directory. Cases and oracle are copied before any provider call.
The fresh-builder arm deliberately starts with no registered tools on every week.
"""
import argparse
import csv
import io
import json
from pathlib import Path
import statistics
import time

from .builder import CodexBuilder
from .contracts import canonical, contract_id, digest
from .engine import Harness
from .jev import Jev, credentials
from .runner import Runner
from .store import Store
from .templates import CSV, CSV_SOURCE


CASES_PATH = Path(__file__).resolve().parent.parent / 'evidence/weekly-csv-20260924/cases.json'
ARMS = ('fixed_script', 'casajev', 'fresh_builder')


def rows_or_stop(payload):
    rows = list(csv.reader(io.StringIO(payload), strict=True))
    if not rows:
        raise ValueError('Missing header')
    width = len(rows[0])
    if any(len(row) != width for row in rows[1:]):
        raise ValueError('Inconsistent CSV width')
    return rows


def fixed_script(case):
    rows = rows_or_stop(case['csv'])
    if case['family'] == 'reuse':
        buckets = {}
        for index, row in enumerate(rows[1:], 1):
            buckets.setdefault(tuple(row), []).append(index)
        groups = [group for group in buckets.values() if len(group) > 1]
        return {'groups': groups, 'records': len(rows)-1,
                'extra_duplicates': sum(len(group)-1 for group in groups)}
    if case['family'] == 'new_rule':
        buckets = {}
        for index, row in enumerate(rows[1:], 1):
            buckets.setdefault(tuple(cell.strip().casefold() for cell in row), []).append(index)
        groups = [group for group in buckets.values() if len(group) > 1]
        return {'groups': groups, 'records': len(rows)-1,
                'extra_duplicates': sum(len(group)-1 for group in groups)}
    if rows[0] != ['kunde', 'region', 'betrag']:
        raise ValueError('Unexpected header')
    totals = {}
    for customer, region, amount in rows[1:]:
        value = int(amount)
        if region == 'Nord':
            totals[customer] = totals.get(customer, 0) + value
    return totals


def score(case, state, events, prior_tools, current_tools):
    status, result = state['status'], state.get('result')
    completed = status == 'completed'
    correct = completed and canonical(result) == canonical(case['expected'])
    halted = status == 'invalid_input' and result is None
    if case['expected_status'] == 'halted':
        passed = halted
    else:
        passed = correct
    registered = [event for event in events if event['kind'] == 'tool_registered']
    used = [event for event in events if event['kind'] == 'tool_completed']
    expected_new = case['expected_new_capability']
    new_capability = bool(registered)
    # A newly built tool is not required for the fixed program; its logic is prepared.
    return {'passed': passed, 'correct_result': correct, 'halted': halted,
            'false_completion': completed and not correct,
            'new_capability': new_capability, 'capability_choice_correct':
                (new_capability == expected_new),
            'registered_count': len(registered), 'executed_count': len(used),
            'registry_size_before': prior_tools, 'registry_size_after': current_tools,
            'used_tool_ids': [event['body']['tool'] for event in used]}


def run_fixed(case):
    started = time.monotonic()
    state = {'status': 'completed', 'result': None, 'builds': 0, 'builder_calls': 0, 'jev_calls': 0}
    try:
        state['result'] = fixed_script(case)
    except (ValueError, csv.Error) as exc:
        state.update(status='invalid_input', error=type(exc).__name__ + ': ' + str(exc))
    return state, [], time.monotonic()-started, 0, 0


def run_harness(case, arm, root, runner, key, store):
    jev = Jev(key)
    builder = CodexBuilder(root/'builder-tmp', model='gpt-5.6-terra', reasoning='low', timeout=120)
    # use_templates=False prevents hidden template construction in either agent arm.
    harness = Harness(store, jev, runner, builder, use_templates=False, use_graph=False,
                      max_steps=18, max_builds=2, max_jev_calls=18, max_builder_calls=4,
                      max_seconds=480)
    task = {'goal': case['goal'], 'objects': {'weekly_export': {
        'kind': 'csv', 'description': 'Wochenexport; unveränderter CSV-Text', 'value': case['csv']}}}
    started = time.monotonic()
    state = harness.create(task)
    state = harness.run(state['id'])
    events = store.events(state['id'])
    return state, events, time.monotonic()-started


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--credentials-file', required=True)
    args = parser.parse_args()
    root = Path(args.output).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise SystemExit('Output directory must be empty; prior evidence is never overwritten.')
    cases_bytes = CASES_PATH.read_bytes()
    cases = json.loads(cases_bytes)
    (root/'cases.json').write_bytes(cases_bytes)
    protocol = {
        'cases_sha256': digest(cases), 'arms': ARMS,
        'order': 'Five weeks in listed order; fixed script, CasaJev, fresh builder per week.',
        'oracle': 'Expected values are stored in cases.json and never passed to the harness.',
        'casajev': 'Shared registry across weeks; only exact duplicate tool seeded before week 1.',
        'fresh_builder': 'New empty registry each week; no templates and no prior tools.',
        'fixed_script': 'Prepared deterministic functions; development time is not measured.',
        'timing': 'Per-task wall time includes model decisions, tool build and verification, execution and persistence. Initial seeded-tool verification is reported separately.',
        'limits': {'steps': 18, 'builds': 2, 'jev_calls': 18, 'builder_calls': 4, 'seconds': 480},
        'acceptance': 'Exact JSON match for valid cases; invalid input must halt with no result. Capability decisions are reported separately.',
        'code_hashes': {name: digest(Path(__file__).with_name(name).read_text())
                        for name in ('weekly_csv_eval.py', 'engine.py', 'builder.py', 'runner.py')},
        'scope': 'Synthetic preflight only; no claim about real anonymized weekly work.'}
    (root/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2)+'\n')
    runner = Runner()
    seed_started = time.monotonic()
    seed_evidence = runner.verify(CSV, CSV_SOURCE)
    seed_seconds = time.monotonic()-seed_started
    cas_store = Store(root/'private-runs'/'casajev')
    cas_store.register(CSV, CSV_SOURCE, seed_evidence)
    key = credentials(args.credentials_file)
    records = []
    for case in cases:
        for arm in ARMS:
            if arm == 'fixed_script':
                state, events, seconds, before, after = run_fixed(case)
            else:
                store = cas_store if arm == 'casajev' else Store(root/'private-runs'/'fresh_builder'/case['id'])
                before = len(store.tools())
                state, events, seconds = run_harness(case, arm, root, runner, key, store)
                after = len(store.tools())
            evaluation = score(case, state, events, before, after)
            if arm == 'fixed_script':
                evaluation['capability_choice_correct'] = None
            record = {'case': case['id'], 'family': case['family'], 'arm': arm,
                      'seconds': seconds, 'status': state['status'], 'result': state.get('result'),
                      'error': state.get('error') or state.get('message'),
                      'builds': state.get('builds', 0), 'builder_calls': state.get('builder_calls', 0),
                      'jev_calls': state.get('jev_calls', 0), 'evaluation': evaluation,
                      'events': events}
            records.append(record)
            (root/'results.json').write_text(json.dumps(records, ensure_ascii=False, indent=2)+'\n')
            print(json.dumps({k:record[k] for k in ('case','arm','status','seconds','builds','builder_calls','jev_calls')}
                             | {'passed': evaluation['passed']}, ensure_ascii=False), flush=True)
    summary = {'seed_verification_seconds': seed_seconds, 'seed_source_hash': digest(CSV_SOURCE), 'arms': {}}
    for arm in ARMS:
        subset = [row for row in records if row['arm'] == arm]
        summary['arms'][arm] = {
            'passed': sum(row['evaluation']['passed'] for row in subset), 'total': len(subset),
            'false_completions': sum(row['evaluation']['false_completion'] for row in subset),
            'total_seconds': sum(row['seconds'] for row in subset),
            'median_seconds': statistics.median(row['seconds'] for row in subset),
            'builds': sum(row['builds'] for row in subset),
            'builder_calls': sum(row['builder_calls'] for row in subset),
            'jev_calls': sum(row['jev_calls'] for row in subset)}
    (root/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
