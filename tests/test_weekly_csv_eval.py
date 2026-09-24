import json
from pathlib import Path

import pytest

from casajev.weekly_csv_eval import CASES_PATH, fixed_script, score
from casajev.engine import Harness, validate_csv_shape
from casajev.jev import DemoJev
from casajev.templates import CSV_SOURCE
from casajev.runner import Runner
from casajev.store import Store
from casajev.templates import CSV


def test_frozen_cases_have_independent_fixed_script_results():
    cases = json.loads(CASES_PATH.read_text())
    assert [case['family'] for case in cases] == [
        'reuse', 'reuse', 'new_rule', 'multi_step', 'invalid_input']
    for case in cases[:-1]:
        assert fixed_script(case) == case['expected']
    with pytest.raises(ValueError, match='width'):
        fixed_script(cases[-1])


def test_changed_rule_cannot_be_satisfied_by_seeded_exact_tool():
    case = json.loads(CASES_PATH.read_text())[2]
    exact_result = Runner().run(CSV_SOURCE, case['csv'])
    assert exact_result != case['expected']
    assert exact_result['groups'] == []


def test_false_completion_and_partial_invalid_result_fail_scoring():
    case = json.loads(CASES_PATH.read_text())[-1]
    assert not score(case, {'status': 'completed', 'result': {'Ada': 17}}, [], 1, 1)['passed']
    assert not score(case, {'status': 'failed', 'result': {'Ada': 10}}, [], 1, 1)['passed']
    assert not score(case, {'status': 'failed', 'result': None}, [], 1, 1)['passed']
    assert score(case, {'status': 'invalid_input', 'result': None}, [], 1, 1)['passed']


def test_malformed_csv_stops_before_tool_and_keeps_registered_source(tmp_path):
    case = json.loads(CASES_PATH.read_text())[-1]
    runner = Runner()
    store = Store(tmp_path)
    store.register(CSV, CSV_SOURCE, runner.verify(CSV, CSV_SOURCE))
    harness = Harness(store, DemoJev(), runner, use_templates=False)
    state = harness.create({'goal': 'Finde exakte Dubletten.', 'objects': {
        'input': {'kind': 'csv', 'description': 'Fehlerhafter Export', 'value': case['csv']}}})
    result = harness.run(state['id'])
    assert result['status'] == 'invalid_input'
    assert result['result'] is None and result['builds'] == 0
    assert len(store.tools()) == 1
    assert not any(event['kind'] == 'tool_started' for event in store.events(state['id']))
