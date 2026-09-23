"""Bounded decision controller shared by data and browser loops.

The controller deliberately owns state reduction, confidence/risk gating and
escalation routing. Providers only rank the finite actions they are given.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Protocol

from .contracts import digest
from .jev import choice


RISK_THRESHOLDS = {
    'passive': 0.55,
    'read': 0.65,
    'compute': 0.65,
    'submit': 0.80,
    'write': 0.80,
    'destructive': 0.95,
    'critical': 0.99,
}


class EscalationTrigger(str, Enum):
    START_MISSION = 'start_mission'
    LOW_CONFIDENCE = 'low_confidence'
    UNKNOWN_STATE = 'unknown_state'
    NO_VALID_ACTION = 'no_valid_action'
    NEEDS_FREE_TEXT = 'needs_free_text'
    GOAL_CHANGED = 'goal_changed'
    RECOVERY_FAILED = 'recovery_failed'


def _compact(value: Any, *, depth: int = 0) -> Any:
    """Produce a deterministic, bounded observation rather than raw-world data."""
    if depth >= 3:
        return {'type': type(value).__name__, 'digest': digest(value)}
    if value is None or type(value) in (bool, int, float):
        return value
    if isinstance(value, str):
        return value if len(value) <= 600 else value[:600] + f'… [{len(value)} chars]'
    if isinstance(value, list):
        return {'type': 'list', 'count': len(value),
                'items': [_compact(item, depth=depth + 1) for item in value[:8]],
                'digest': digest(value)}
    if isinstance(value, dict):
        keys = sorted(value, key=str)
        return {'type': 'object', 'count': len(value),
                'fields': {str(key): _compact(value[key], depth=depth + 1) for key in keys[:12]},
                'digest': digest(value)}
    return {'type': type(value).__name__, 'preview': str(value)[:200]}


class StateCompiler:
    """Compiles persisted mission state into the small state seen by a policy."""
    def compile(self, mission: Mapping[str, Any], actions: Mapping[str, Any]) -> dict:
        objects = {}
        for ref, obj in mission.get('objects', {}).items():
            objects[ref] = {'kind': obj.get('kind'), 'description': obj.get('description', ''),
                            'value': _compact(obj.get('value'))}
        observations = []
        for item in mission.get('observations', [])[-5:]:
            observations.append({key: _compact(item[key]) for key in
                ('tool', 'input_ref', 'output_ref', 'result', 'validated', 'validation') if key in item})
        extra = {key: _compact(mission[key]) for key in
                 ('clarification', 'capability_request', 'available_tools',
                  'available_data_tools', 'external_tools', 'available_external_tools',
                  'workflow_graph', 'temporary_failure') if mission.get(key) is not None}
        if mission.get('conversation'):
            extra['conversation'] = _compact(mission['conversation'][-8:])
        return {
            'goal': mission.get('goal') or mission.get('trusted_goal'),
            'phase': mission.get('phase', 'decide'),
            'constraints': {'permissions': list(mission.get('permissions', [])),
                            'execution_mode': mission.get('execution_mode', 'standard')},
            'objects': objects,
            'observations': observations,
            'last_action': mission.get('last_action'),
            'last_result': _compact(mission.get('result')) if mission.get('result') is not None else None,
            'available_actions': {key: _compact(value) for key, value in actions.items()},
            'context': extra,
        }


@dataclass
class Decision:
    action: str | None
    confidence: float
    distribution: dict[str, float] = field(default_factory=dict)
    answers: dict[str, Any] = field(default_factory=dict)
    threshold: float = 0.65
    risk: str = 'compute'
    accepted: bool = False
    reason: str | None = None


class DecisionPolicy(Protocol):
    def decide(self, *, state: dict, actions: Mapping[str, Any], goal: str,
               instructions: str = 'Select the next action.', questions: Mapping[str, Any] | None = None,
               decision_key: str = 'action') -> Decision: ...


class JevDecisionPolicy:
    """Adapter that keeps TypeSafe/Jev replaceable behind one stable contract."""
    def __init__(self, jev):
        self.jev = jev

    @property
    def mode(self):
        return getattr(self.jev, 'mode', 'jev')

    @property
    def last(self):
        return getattr(self.jev, 'last', None)

    def decide(self, *, state, actions, goal, instructions='Select the next action.', questions=None, decision_key='action'):
        query = dict(questions or {})
        query[decision_key] = choice(instructions, actions)
        answers = self.jev.ask(state, query)
        action = answers.get(decision_key)
        confidence = 1.0 if action is not None else 0.0
        distribution = {}
        response = (getattr(self.jev, 'last', None) or {}).get('response', {})
        raw = response.get('answers', {}).get(decision_key, {}) if isinstance(response, dict) else {}
        if isinstance(raw, dict):
            raw_choice = raw.get('choice')
            if raw_choice in actions:
                action = raw_choice
            raw_confidence = raw.get('confidence')
            if type(raw_confidence) in (int, float):
                confidence = float(raw_confidence)
            probabilities = raw.get('probabilities')
            if isinstance(probabilities, dict):
                distribution = {str(key): float(value) for key, value in probabilities.items()
                                if type(value) in (int, float)}
        return Decision(action=action, confidence=confidence, distribution=distribution, answers=answers)


class ConfidenceGate:
    def __init__(self, thresholds=None):
        self.thresholds = {**RISK_THRESHOLDS, **(thresholds or {})}

    @staticmethod
    def risk_for(action, actions):
        spec = actions.get(action, {}) if action is not None else {}
        return spec.get('risk', 'compute') if isinstance(spec, dict) else 'compute'

    def apply(self, decision, actions):
        decision.risk = self.risk_for(decision.action, actions)
        decision.threshold = self.thresholds.get(decision.risk, self.thresholds['compute'])
        decision.accepted = decision.action in actions and decision.confidence >= decision.threshold
        if not decision.accepted:
            decision.reason = 'no_valid_action' if decision.action not in actions else 'low_confidence'
        return decision


class DecisionController:
    def __init__(self, policy, *, compiler=None, gate=None):
        self.policy = policy
        self.compiler = compiler or StateCompiler()
        self.gate = gate or ConfidenceGate()

    def choose(self, mission, actions, instructions, questions=None, decision_key='action'):
        state = self.compiler.compile(mission, actions)
        decision = self.policy.decide(state=state, actions=actions,
                                      goal=state.get('goal') or '', instructions=instructions,
                                      questions=questions, decision_key=decision_key)
        return self.gate.apply(decision, actions), state


class FastLoop:
    """Generic observe -> compile -> decide -> gate -> execute loop."""
    def __init__(self, controller, *, max_steps=20):
        self.controller, self.max_steps = controller, max_steps

    def run(self, *, goal: str, observe: Callable[[], dict],
            actions: Callable[[dict], Mapping[str, Any]],
            execute: Callable[[str, dict], Any], terminal: Callable[[dict], bool],
            instructions: str, escalate: Callable[[str, dict, Mapping[str, Any], Decision], str | None] | None = None,
            on_step: Callable[[dict], None] | None = None):
        trace = []
        for index in range(self.max_steps):
            raw = observe()
            if terminal(raw):
                return {'status': 'completed', 'state': raw, 'trace': trace}
            available = dict(actions(raw))
            mission = {**raw, 'goal': goal, 'last_action': trace[-1]['action'] if trace else None}
            decision, compiled = self.controller.choose(mission, available, instructions)
            action = decision.action if decision.accepted else None
            routed = False
            if action is None and escalate is not None:
                action = escalate(decision.reason or 'unknown_state', compiled, available, decision)
                routed = action in available
            step = {'index': index, 'action': action, 'confidence': decision.confidence,
                    'threshold': decision.threshold, 'risk': decision.risk,
                    'distribution': decision.distribution, 'escalated': routed}
            trace.append(step)
            if on_step:
                on_step(step)
            if action not in available:
                return {'status': 'needs_supervisor', 'reason': decision.reason,
                        'state': raw, 'trace': trace}
            execute(action, raw)
        return {'status': 'budget_exhausted', 'state': observe(), 'trace': trace}
