"""A chosen ask_user action can yield a bounded, source-grounded question."""
from casajev.builder import CodexBuilder
from casajev.engine import Harness
from casajev.runner import Runner
from casajev.store import Store


class AskJev:
    mode = 'ask-fixture'
    last = None

    def ask(self, state, questions):
        return {'action': 'ask_user'}


class Clarifier:
    last = {'backend': 'test-clarifier'}

    def __init__(self):
        self.calls = []

    def clarify(self, context):
        self.calls.append(context)
        return 'Soll Invoice Date oder Settlement Date das Feld date füllen?'


def task():
    return {'goal': 'Choose the date for the output; two source dates are possible.',
            'objects': {'source_csv': {'kind': 'csv', 'description': 'Export',
                                       'value': 'Invoice Date,Settlement Date,Net\n2026-09-01,2026-09-02,10\n'}},
            'permissions': ['compute']}


def test_ask_user_uses_optional_clarifier_with_budget_and_audit(tmp_path):
    builder = Clarifier()
    harness = Harness(Store(tmp_path), AskJev(), Runner(), builder,
                      use_templates=False, use_graph=False, max_builder_calls=1)
    created = harness.create(task())
    state = harness.run(created['id'])
    assert state['status'] == 'needs_input'
    assert state['message'] == 'Soll Invoice Date oder Settlement Date das Feld date füllen?'
    assert state['builder_calls'] == 1 and state['result'] is None and not state['observations']
    assert len(builder.calls) == 1
    assert builder.calls[0]['goal'] == task()['goal']
    assert 'Invoice Date' in builder.calls[0]['objects']['source_csv']['value']
    assert builder.calls[0]['available_actions'] == {}
    kinds = [event['kind'] for event in harness.store.events(created['id'])]
    assert 'builder_result' in kinds and 'clarification_drafted' in kinds and 'needs_input' in kinds


def test_ask_user_falls_back_without_builder_or_remaining_budget(tmp_path):
    for name, builder, budget in [('missing', None, 1), ('exhausted', Clarifier(), 0)]:
        harness = Harness(Store(tmp_path / name), AskJev(), Runner(), builder,
                          use_templates=False, use_graph=False, max_builder_calls=budget)
        created = harness.create(task())
        state = harness.run(created['id'])
        assert state['status'] == 'needs_input'
        assert state['message'] == 'Specify the desired result more precisely.'
        assert state['builder_calls'] == 0 and state['result'] is None
        if builder:
            assert not builder.calls


def test_jev_only_mode_never_calls_clarifier(tmp_path):
    builder = Clarifier()
    harness = Harness(Store(tmp_path), AskJev(), Runner(), builder,
                      use_templates=False, use_graph=False, execution_mode='jev_only')
    created = harness.create(task())
    state = harness.run(created['id'])
    assert state['status'] == 'needs_input'
    assert state['message'] == 'Specify the desired result more precisely.'
    assert state['builder_calls'] == 0 and not builder.calls


def test_invalid_optional_clarification_falls_back_without_completion(tmp_path):
    builder = Clarifier()
    builder.clarify = lambda context: 'An unbounded statement without a question'
    harness = Harness(Store(tmp_path), AskJev(), Runner(), builder,
                      use_templates=False, use_graph=False)
    created = harness.create(task())
    state = harness.run(created['id'])
    assert state['status'] == 'needs_input' and state['result'] is None
    assert state['message'] == 'Specify the desired result more precisely.'
    assert state['builder_calls'] == 1
    assert 'clarification_unavailable' in [event['kind'] for event in harness.store.events(created['id'])]


def test_builder_clarification_prompt_only_asks_from_bounded_context(tmp_path):
    builder = CodexBuilder(tmp_path, model='gpt-6-sol')
    prompts = []

    def capture(prompt, schema):
        prompts.append(prompt)
        return {'question': 'Welches Datumsfeld soll date füllen?'}

    builder.invoke = capture
    assert builder.clarify({'goal': 'Choose date', 'objects': {}}) == 'Welches Datumsfeld soll date füllen?'
    assert 'name concrete ambiguous field or option names only when they are actually visible' in prompts[0]
    assert 'Do not execute anything, create a tool or contract' in prompts[0]
