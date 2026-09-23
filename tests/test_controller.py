import pytest

from casajev.controller import (ConfidenceGate, Decision, DecisionController,
                                FastLoop, StateCompiler)
from casajev.laya import LayaCapacityError, LayaDecisionPolicy
from casajev.realtime import RealtimeController, from_settings
from casajev.settings import save_settings
from casajev.jev import DemoJev


class FixedPolicy:
    def __init__(self, action, confidence=1.0):
        self.action, self.confidence = action, confidence

    def decide(self, **kwargs):
        return Decision(action=self.action, confidence=self.confidence,
                        distribution={self.action: self.confidence},
                        answers={'action': self.action})


def test_state_compiler_bounds_raw_world_and_keeps_recent_observations():
    raw = {'goal':'Inspect records', 'permissions':['compute'],
           'objects':{'rows':{'kind':'text','description':'large input','value':'x'*5000}},
           'observations':[{'tool':str(i),'result':list(range(20))} for i in range(9)]}
    compiled = StateCompiler().compile(raw, {'inspect':{'description':'Inspect','risk':'read'}})
    assert compiled['goal'] == 'Inspect records'
    assert len(compiled['objects']['rows']['value']) < 700
    assert [item['tool'] for item in compiled['observations']] == ['4','5','6','7','8']
    assert compiled['available_actions']['inspect']['fields']['risk'] == 'read'


def test_risk_gate_uses_action_specific_threshold():
    actions = {'scroll':{'risk':'passive'}, 'submit':{'risk':'submit'},
               'delete':{'risk':'destructive'}}
    gate = ConfidenceGate()
    assert gate.apply(Decision('scroll', .56), actions).accepted
    assert not gate.apply(Decision('submit', .79), actions).accepted
    assert gate.apply(Decision('submit', .80), actions).accepted
    assert not gate.apply(Decision('delete', .94), actions).accepted


def test_fast_loop_routes_uncertainty_to_bounded_escalation():
    world = {'done':False,'executed':[]}
    loop = FastLoop(DecisionController(FixedPolicy('open', .60)), max_steps=2)

    def execute(action, _state):
        world['executed'].append(action)
        world['done'] = True

    result = loop.run(goal='Open source',
        observe=lambda:{'permissions':['public_web_read'],'objects':{},
                        'observations':[],'done':world['done']},
        actions=lambda _state:{'open':{'risk':'read'},'show':{'risk':'passive'}},
        execute=execute, terminal=lambda _state:world['done'], instructions='Choose.',
        escalate=lambda trigger,_state,_actions,_decision:'show' if trigger=='low_confidence' else None)
    assert result['status'] == 'completed'
    assert world['executed'] == ['show']
    assert result['trace'][0]['escalated'] is True


def test_decision_policy_is_replaceable_without_changing_controller():
    controller = DecisionController(FixedPolicy('local_action', .9))
    decision, _state = controller.choose({'goal':'Test','objects':{},'observations':[]},
        {'local_action':{'risk':'compute'}}, 'Choose.')
    assert decision.accepted and decision.action == 'local_action'


class FakeLayaRouter:
    def __init__(self, pick=None, confidence=.91):
        self.pick, self.confidence, self.calls = pick, confidence, []

    def load(self, model):
        return self

    def predict(self, state, questions, model=None):
        self.calls.append((state, questions, model))
        answers = {}
        for key, question in questions.items():
            options = list(question['criteria'])
            selected = self.pick if self.pick in options else options[0]
            remaining = (1 - self.confidence) / max(1, len(options) - 1)
            probabilities = {option: (self.confidence if option == selected else remaining) for option in options}
            answers[key] = {'type':'choice', 'choice':selected, 'probabilities':probabilities,
                            'confidence':self.confidence}
        return {'answers':answers, 'routing':{'model':model}, 'usage':{'tokens':10}}


def test_laya_policy_validates_and_returns_typed_decision():
    router = FakeLayaRouter('stop')
    policy = LayaDecisionPolicy(router=router, max_actions=20)
    decision = policy.decide(state={'temperature':80}, goal='cool',
        actions={'observe':{'risk':'read'}, 'stop':{'risk':'passive'}}, instructions='Choose')
    assert decision.action == 'stop'
    assert decision.confidence == .91
    assert decision.answers['action'] == 'stop'
    assert policy.last['provider'] == 'laya'


def test_laya_policy_routes_large_action_space_in_two_bounded_calls():
    router = FakeLayaRouter()
    policy = LayaDecisionPolicy(router=router, max_actions=10)
    actions = {f'a{i}': {'description':f'action {i}', 'risk':'compute'} for i in range(35)}
    decision = policy.decide(state={'goal':'pick'}, goal='pick', actions=actions, instructions='Choose')
    assert decision.action in actions
    assert len(router.calls) == 2
    assert max(len(call[1][next(iter(call[1]))]['criteria']) for call in router.calls) <= 10
    assert policy.last['hierarchical_routing']['candidate_count'] == 35


def test_laya_policy_rejects_unbounded_action_space():
    policy = LayaDecisionPolicy(router=FakeLayaRouter(), max_actions=10)
    actions = {f'a{i}': {} for i in range(101)}
    with pytest.raises(LayaCapacityError):
        policy.decide(state={}, goal='', actions=actions)


def test_realtime_controller_never_executes_late_decision():
    clock_values = iter([10.0, 10.8])
    policy = FixedPolicy('go', .95)
    loop = RealtimeController(DecisionController(policy), deadline_ms=500,
                              max_age_ms=200, safe_action='stop', clock=lambda: next(clock_values))
    result = loop.step(observation={'goal':'move'}, actions={
        'go': {'risk':'compute'}, 'stop': {'risk':'passive'}}, instructions='Choose', observed_at=10.0)
    assert result['action'] == 'stop'
    assert result['reason'] == 'deadline_missed'
    assert loop.metrics.snapshot()['deadline_misses'] == 1


def test_realtime_controller_rejects_stale_observation_without_policy_call():
    clock_values = iter([5.0])
    policy = FixedPolicy('go', .95)
    loop = RealtimeController(DecisionController(policy), deadline_ms=500,
                              max_age_ms=100, safe_action='stop', clock=lambda: next(clock_values))
    result = loop.step(observation={'goal':'move'}, actions={
        'go': {'risk':'compute'}, 'stop': {'risk':'passive'}}, instructions='Choose', observed_at=4.0)
    assert result['action'] == 'stop'
    assert result['reason'] == 'stale_observation'


def test_realtime_factory_uses_its_own_pipeline_setting(tmp_path):
    save_settings(tmp_path, {'general_decision_provider':'jev',
                             'realtime_decision_provider':'laya'})
    loop=from_settings(tmp_path, jev=DemoJev())
    assert loop.controller.policy.mode=='laya-local'
