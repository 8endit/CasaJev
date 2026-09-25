"""Real stdio MCP regression tests for connector catalogue boundaries."""
import json
from pathlib import Path
import sys

import pytest

from casajev.connectors import Connectors, ConnectorContractError
from casajev.contracts import digest
from casajev.engine import Harness
from casajev.library import Library
from casajev.runner import Runner
from casajev.store import Store


INPUT = {'type': 'object', 'properties': {'query': {'type': 'string'}},
         'required': ['query'], 'additionalProperties': False}
OUTPUT = {'type': 'object', 'properties': {'found': {'type': 'string'}},
          'required': ['found'], 'additionalProperties': False}


def scenario(input_schema=None, output_schema=None, response=None):
    return {'descriptor': {'name': 'lookup', 'description': 'Read fixture lookup',
                           'inputSchema': input_schema or INPUT,
                           'outputSchema': output_schema if output_schema is not None else OUTPUT},
            'response': response if response is not None else {'found': 'pear'}}


class FixedJev:
    mode = 'controlled-mcp-policy'
    last = None

    def ask(self, state, questions):
        if state['observations']:
            return {'action': 'done'}
        options = [key for key in questions['action']['criteria'] if key.startswith('external:')]
        return {'action': options[0] if options else 'need_capability'}


def prepared(tmp_path):
    path = tmp_path / 'scenario.json'
    log = tmp_path / 'mcp.jsonl'
    path.write_text(json.dumps(scenario()))
    store = Store(tmp_path / 'store')
    manager = Connectors(Library(store))
    identity = manager.save({'name': 'Drift fixture', 'command': sys.executable,
                             'args': [str(Path(__file__).with_name('mcp_contract_stub.py')),
                                      str(path), str(log)], 'env': {}})
    manager.inspect(identity)
    manager.save({'id': identity, 'enabled': True, 'read_only': True,
                  'allowed_tools': ['lookup']})
    tool_id, tool = next(iter(manager.tools().items()))
    harness = Harness(store, FixedJev(), Runner(), connectors=manager,
                      execution_mode='jev_only', use_graph=False,
                      max_steps=5, max_jev_calls=5, max_seconds=30)
    task = harness.create({'goal': 'Read query pear from the approved lookup',
                           'objects': {'args': {'kind': 'json', 'description': 'query',
                                                'value': {'query': 'pear'}}},
                           'permissions': ['external_read']})
    return path, log, manager, identity, tool_id, tool, harness, task


def change(path, body):
    path.write_text(json.dumps(body))


def calls(log):
    return [json.loads(line)['request']['method'] for line in log.read_text().splitlines()]


def test_optional_input_extension_preserves_selection_and_reuses_old_request(tmp_path):
    path, log, manager, identity, _, old, harness, task = prepared(tmp_path)
    try:
        widened = {'type': 'object', 'properties': {**INPUT['properties'],
                   'locale': {'type': 'string'}}, 'required': ['query'], 'additionalProperties': False}
        change(path, scenario(input_schema=widened))
        state = harness.run(task['id'])
        assert state['status'] == 'completed_unverified'
        assert state['verification'] == 'no_goal_oracle'
        assert state['result'] == {'found': 'pear'}
        assert len(state['seen_calls']) == 2  # selected and executed snapshot identities
        assert state['observations'][0]['selected_schema_hash'] == old['schema_hash']
        assert state['observations'][0]['executed_schema_hash'] != old['schema_hash']
        assert manager.get(identity)['enabled'] is True
        assert next(iter(manager.tools().values()))['schema_hash'] != old['schema_hash']
        assert calls(log).count('tools/call') == 1
    finally:
        manager.close()


def test_required_input_change_fails_closed_before_call(tmp_path):
    path, log, manager, identity, _, _, harness, task = prepared(tmp_path)
    try:
        changed = {'type': 'object', 'properties': {**INPUT['properties'],
                   'scope': {'type': 'string'}}, 'required': ['query', 'scope'],
                   'additionalProperties': False}
        change(path, scenario(input_schema=changed))
        state = harness.run(task['id'])
        assert state['status'] == 'needs_review' and state['outcome_kind'] == 'contract_failure'
        assert state['result'] is None and not state['observations']
        assert manager.get(identity)['enabled'] is False
        assert 'tools/call' not in calls(log)
    finally:
        manager.close()


def test_open_object_schema_does_not_claim_optional_addition_is_compatible(tmp_path):
    path, log, manager, identity, _, _, harness, task = prepared(tmp_path)
    try:
        open_old = {'type': 'object', 'properties': INPUT['properties'], 'required': ['query']}
        change(path, scenario(input_schema=open_old))
        manager.inspect(identity)
        manager.save({'id': identity, 'enabled': True, 'read_only': True,
                      'allowed_tools': ['lookup']})
        widened = {'type': 'object', 'properties': {**INPUT['properties'],
                   'locale': {'type': 'string'}}, 'required': ['query']}
        change(path, scenario(input_schema=widened))
        state = harness.run(task['id'])
        assert state['status'] == 'needs_review' and state['outcome_kind'] == 'contract_failure'
        assert manager.get(identity)['enabled'] is False
        assert 'tools/call' not in calls(log)
    finally:
        manager.close()


def test_output_schema_change_fails_closed_before_call(tmp_path):
    path, log, manager, identity, _, _, harness, task = prepared(tmp_path)
    try:
        change(path, scenario(output_schema={'type': 'string'}, response='pear'))
        state = harness.run(task['id'])
        assert state['status'] == 'needs_review' and state['outcome_kind'] == 'contract_failure'
        assert manager.get(identity)['enabled'] is False
        assert 'tools/call' not in calls(log)
    finally:
        manager.close()


def test_output_value_must_satisfy_inspected_schema(tmp_path):
    path, log, manager, _, _, _, harness, task = prepared(tmp_path)
    try:
        change(path, scenario(response='pear'))
        state = harness.run(task['id'])
        assert state['status'] == 'needs_review' and state['outcome_kind'] == 'contract_failure'
        assert state['result'] is None and not state['observations']
        assert calls(log).count('tools/call') == 1
    finally:
        manager.close()


def test_silent_semantic_change_stays_unverified(tmp_path):
    path, _, manager, _, _, _, harness, task = prepared(tmp_path)
    try:
        change(path, scenario(response={'found': 'plum'}))
        state = harness.run(task['id'])
        assert state['status'] == 'completed_unverified'
        assert state['verification'] == 'no_goal_oracle'
        assert state['result'] == {'found': 'plum'}
    finally:
        manager.close()


def test_legacy_catalogue_requires_reinspection_and_reselection(tmp_path):
    _, log, manager, identity, tool_id, tool, _, _ = prepared(tmp_path)
    try:
        config = manager.get(identity)
        legacy = config['tools'][0]
        legacy.pop('output_schema')
        legacy['schema_hash'] = digest(legacy['input_schema'])
        manager.library.put('connectors', config)
        with pytest.raises(ConnectorContractError):
            manager.call(tool_id, {'query': 'pear'}, legacy['schema_hash'])
        assert manager.get(identity)['enabled'] is False
        assert manager.get(identity)['allowed_tools'] == []
        assert 'tools/call' not in calls(log)
    finally:
        manager.close()


def test_legacy_catalogue_cannot_autopreserve_on_optional_extension(tmp_path):
    path, log, manager, identity, tool_id, _, _, _ = prepared(tmp_path)
    try:
        config = manager.get(identity)
        legacy = config['tools'][0]
        legacy.pop('output_schema')
        legacy['schema_hash'] = digest(legacy['input_schema'])
        manager.library.put('connectors', config)
        widened = {'type': 'object', 'properties': {**INPUT['properties'],
                   'locale': {'type': 'string'}}, 'required': ['query'], 'additionalProperties': False}
        change(path, scenario(input_schema=widened))
        with pytest.raises(ConnectorContractError):
            manager.call(tool_id, {'query': 'pear'}, legacy['schema_hash'])
        assert manager.get(identity)['enabled'] is False
        assert 'tools/call' not in calls(log)
    finally:
        manager.close()
