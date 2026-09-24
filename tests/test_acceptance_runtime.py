"""Focused acceptance-path checks without provider calls or evaluation adapters."""
import copy
from casajev.contracts import contract_id, digest
from casajev.engine import Harness, bound_inputs
from casajev.runner import Runner
from casajev.store import Store
from casajev.templates import CSV_COLUMNS, CSV_COLUMNS_SOURCE, CSV, CSV_SOURCE, SORT
import pytest


class HeaderChoice:
    mode = 'test'
    last = {}

    def ask(self, context, questions):
        choices = questions['action']['criteria']
        csv_text = context['objects']['source']['value']
        wanted = ({'vendor':'Supplier','amount':'Net','date':'Day'}
                  if csv_text.startswith('Supplier,') else
                  {'vendor':'Lieferant','amount':'Betrag','date':'Datum'})
        for key, item in choices.items():
            if isinstance(item, dict) and item.get('input_binding') == wanted:
                return {'action':key}
        return {'action':'done'}


def test_reuses_identical_parameterized_tool_with_new_headers(tmp_path):
    store, runner = Store(tmp_path), Runner()
    tool_id = store.register(CSV_COLUMNS, CSV_COLUMNS_SOURCE,
                             runner.verify(CSV_COLUMNS, CSV_COLUMNS_SOURCE))
    harness = Harness(store, HeaderChoice(), runner, use_templates=False, use_graph=False,
                      execution_mode='jev_only')
    cases = [
        ('Supplier,Net,Day\n Acme ,0012.50,2026-09-24\n',
         {'vendor':'Supplier','amount':'Net','date':'Day'},
         {'rows':[{'vendor':' Acme ','amount':'0012.50','date':'2026-09-24'}]}),
        ('Datum,Lieferant,Betrag\n2026-09-25,Öko GmbH,\n',
         {'vendor':'Lieferant','amount':'Betrag','date':'Datum'},
         {'rows':[{'vendor':'Öko GmbH','amount':None,'date':'2026-09-25'}]})]
    observed = []
    for csv_text, mapping, expected in cases:
        task = {'goal':'Read vendor, amount and date according to the CSV headers.',
                'objects': {'source':{'kind':'csv','description':'Original CSV','value':csv_text}},
                'acceptance': {'expected':expected}}
        state = harness.run(harness.create(task)['id'])
        assert state['status'] == 'completed'
        assert state['result'] == expected
        assert state['verification'] == 'task_supplied_expected_result_match'
        assert state['builds'] == 0
        observation = state['observations'][0]
        assert observation['tool'] == tool_id
        assert observation['input_binding'] == mapping
        assert observation['input_hash'] == digest({'csv':csv_text,'columns':mapping})
        assert observation['output_hash'] == digest(expected)
        assert observation['source_hash'] == digest(CSV_COLUMNS_SOURCE)
        assert observation['contract_hash'] == contract_id(CSV_COLUMNS)
        assert state['verification_evidence']['original_objects_hash'] == digest(task['objects'])
        observed.append(observation)
    assert len(store.tools()) == 1
    assert observed[0]['tool'] == observed[1]['tool']


def test_no_oracle_is_terminal_but_unverified(tmp_path):
    store, runner = Store(tmp_path), Runner()
    store.register(CSV_COLUMNS, CSV_COLUMNS_SOURCE, runner.verify(CSV_COLUMNS, CSV_COLUMNS_SOURCE))
    harness = Harness(store, HeaderChoice(), runner, use_graph=False, execution_mode='jev_only')
    state = harness.run(harness.create({'goal':'Read the mapped CSV.', 'objects':{
        'source':{'kind':'csv','description':'Original CSV',
                  'value':'Supplier,Net,Day\nAcme,1,2026-09-24\n'}}})['id'])
    assert state['status'] == 'completed_unverified'
    assert state['outcome_kind'] == 'unverified'
    assert state['verification'] == 'no_goal_oracle'
    assert state['result']['rows'][0]['vendor'] == 'Acme'
    assert harness.run(state['id'])['status'] == 'completed_unverified'


def test_malformed_csv_is_domain_rejection_without_tool_run(tmp_path):
    store, runner = Store(tmp_path), Runner()
    store.register(CSV_COLUMNS, CSV_COLUMNS_SOURCE, runner.verify(CSV_COLUMNS, CSV_COLUMNS_SOURCE))
    harness = Harness(store, HeaderChoice(), runner, use_graph=False, execution_mode='jev_only')
    state = harness.run(harness.create({'goal':'Read mapped CSV', 'objects':{
        'source':{'kind':'csv','description':'Original CSV',
                  'value':'Supplier,Net,Day\nAcme,1\n'}}})['id'])
    assert state['status'] == 'invalid_input'
    assert state['outcome_kind'] == 'domain_rejection'
    assert not state['observations']


@pytest.mark.parametrize('csv_text', [
    'Supplier,Net,Net\nAcme,1,2026-09-24\n',
    'Supplier,Net,Day\nAcme,1,2026-02-30\n'])
def test_ambiguous_header_or_invalid_date_does_not_complete(tmp_path, csv_text):
    store, runner = Store(tmp_path), Runner()
    store.register(CSV_COLUMNS, CSV_COLUMNS_SOURCE, runner.verify(CSV_COLUMNS, CSV_COLUMNS_SOURCE))
    harness = Harness(store, HeaderChoice(), runner, use_graph=False, execution_mode='jev_only')
    state = harness.run(harness.create({'goal':'Read mapped CSV', 'objects':{
        'source':{'kind':'csv','description':'Original CSV','value':csv_text}}})['id'])
    if csv_text.startswith('Supplier,Net,Net'):
        # This header is ambiguous for this tool, but may suit another contract.
        assert state['status'] == 'needs_review'
    else:
        assert state['status'] == 'invalid_input'
        assert state['outcome_kind'] == 'domain_rejection'
    assert state['result'] is None
    if '2026-02-30' in csv_text:
        assert state['rejection_verified'] is False


def test_verifier_timeout_is_not_a_contract_repair(tmp_path):
    runner = Runner()
    harness = Harness(Store(tmp_path), HeaderChoice(), runner, use_graph=False)
    state = harness.create({'goal':'Read CSV', 'objects':{}})
    state.update(phase='verify', pending_spec=CSV_COLUMNS, pending_source=CSV_COLUMNS_SOURCE)
    harness.store.save(state)
    runner.verify = lambda *args: (_ for _ in ()).throw(TimeoutError('verifier timed out'))
    result = harness.run(state['id'])
    assert result['status'] == 'failed'
    assert result['outcome_kind'] == 'verifier_error'
    assert result['phase'] == 'verify'
    assert not harness.store.tools()


def test_tool_value_error_quarantines_defective_source(tmp_path):
    source = 'def main(payload):\n    if payload == [9]: raise ValueError("bug")\n    return sorted(payload)\n'
    store, runner = Store(tmp_path), Runner()
    tool_id = store.register(SORT, source, runner.verify(SORT, source))
    class PickTool:
        mode = 'test'
        last = {}
        def ask(self, context, questions):
            choices = questions['action']['criteria']
            return {'action':next(k for k in choices if k.startswith('use:'))}
    harness = Harness(store, PickTool(), runner, use_graph=False, execution_mode='jev_only')
    state = harness.run(harness.create({'goal':'Sort numbers', 'objects':{
        'numbers':{'kind':'numbers','description':'Numbers','value':[9]}}})['id'])
    assert state['status'] == 'failed'
    assert state['outcome_kind'] == 'contract_failure'
    assert tool_id not in store.tools()


def test_new_mapping_contract_does_not_block_old_duplicate_contract(tmp_path):
    store, runner = Store(tmp_path), Runner()
    old_id = store.register(CSV, CSV_SOURCE, runner.verify(CSV, CSV_SOURCE))
    store.register(CSV_COLUMNS, CSV_COLUMNS_SOURCE, runner.verify(CSV_COLUMNS, CSV_COLUMNS_SOURCE))
    class PickDuplicate:
        mode = 'test'
        last = {}
        def ask(self, context, questions):
            options = questions['action']['criteria']
            for key, item in options.items():
                if isinstance(item, dict) and item.get('tool') == old_id:
                    return {'action':key}
            return {'action':'done'}
    harness = Harness(store, PickDuplicate(), runner, use_graph=False, execution_mode='jev_only')
    state = harness.run(harness.create({'goal':'Find exact duplicate records.',
        'objects':{'source':{'kind':'csv','description':'Original CSV',
                             'value':'a,a\nx,y\nx,y\n'}},
        'acceptance':{'expected':{'groups':[[1,2]],'records':2,'extra_duplicates':1}}})['id'])
    assert state['status'] == 'completed'
    assert state['observations'][0]['tool'] == old_id


def test_boolean_json_subschema_is_not_a_mapping_protocol():
    spec = copy.deepcopy(CSV_COLUMNS)
    spec['input_schema']['properties']['csv'] = True
    assert bound_inputs({'kind':'csv','value':'a,b,c\n1,2,3\n'}, spec) == []
