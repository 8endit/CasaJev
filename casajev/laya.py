"""Optional local Laya decision provider.

Laya is deliberately loaded lazily: importing CasaJev must not download a model.
The provider accepts only a bounded finite action set and validates the complete
probability distribution before a decision can reach the controller gate.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Any, Mapping

from .controller import Decision
from .jev import choice

LAYA_REPOSITORY = 'convaiinnovations/laya'
# Reviewed and benchmarked checkpoint snapshot. Updating it is an explicit release change.
LAYA_REVISION = '1c5edc17a7acd8701df6fc341c0d179f1c62c982'
LAYA_SUBFOLDERS = {'english': None, 'multilingual': 'multilingual',
                   'typed-decisions': 'typed-decisions'}

class LayaUnavailable(RuntimeError):
    pass


class LayaCapacityError(ValueError):
    pass


class LayaDecisionPolicy:
    mode = 'laya-local'

    def __init__(self, *, model: str = 'multilingual', device: str = 'cpu',
                 max_actions: int = 20, router=None):
        if not 2 <= max_actions <= 50:
            raise ValueError('Laya max_actions must be between 2 and 50')
        if model not in LAYA_SUBFOLDERS:
            raise ValueError('Unknown Laya checkpoint')
        self.model, self.device, self.max_actions = model, device, max_actions
        self._router = router
        self._lock = threading.Lock()
        self.last = None

    def _load(self):
        if self._router is not None:
            return self._router
        try:
            from laya import Router
            from huggingface_hub import snapshot_download
        except (ImportError, OSError) as exc:
            raise LayaUnavailable(
                'Lokales Laya fehlt. Installiere CasaJev mit dem Extra "local": '
                'uv sync --extra local'
            ) from exc
        subfolder = LAYA_SUBFOLDERS[self.model]
        patterns = ([f'{subfolder}/*'] if subfolder else
                    ['*.json', '*.safetensors', 'encoder/*', 'tokenizer/*'])
        model_root = snapshot_download(LAYA_REPOSITORY, revision=LAYA_REVISION,
                                       allow_patterns=patterns)
        # One explicitly selected, revision-pinned checkpoint stays resident.
        # Preloading all three would exceed the resource budget of many laptops.
        self._router = Router(models={self.model: (model_root, subfolder)},
                              device=self.device, default=self.model, max_loaded=1)
        return self._router

    @staticmethod
    def _decode(answer: Any, options: Mapping[str, Any]):
        if not isinstance(answer, dict) or answer.get('type') != 'choice':
            raise ValueError('Invalid Laya choice answer')
        selected = answer.get('choice')
        probabilities = answer.get('probabilities')
        confidence = answer.get('confidence')
        if selected not in options or not isinstance(probabilities, dict) or set(probabilities) != set(options):
            raise ValueError('Unknown Laya choice or incomplete probabilities')
        values = [confidence, *probabilities.values()]
        if any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1
               for value in values):
            raise ValueError('Invalid Laya confidence')
        if abs(sum(probabilities.values()) - 1) > .011:
            raise ValueError('Laya probabilities do not sum to one')
        if probabilities[selected] + 1e-6 < max(probabilities.values()):
            raise ValueError('Laya choice is not the highest-probability option')
        return selected, float(confidence), {str(key): float(value) for key, value in probabilities.items()}

    def warmup(self):
        router = self._load()
        with self._lock:
            started = time.monotonic()
            router.load(self.model)
            self.last = {'provider': 'laya', 'model': self.model,
                         'load_seconds': time.monotonic() - started, 'warmed': True}
        return dict(self.last)

    def decide(self, *, state: dict, actions: Mapping[str, Any], goal: str,
               instructions: str = 'Select the next action.', questions=None,
               decision_key: str = 'action') -> Decision:
        if len(actions) > self.max_actions * self.max_actions:
            raise LayaCapacityError(
                f'Laya hierarchical action budget exceeded: {len(actions)} > {self.max_actions ** 2}. '
                'Narrow the action set before real-time inference.'
            )
        original_actions = dict(actions)
        page_confidence = 1.0
        page_evidence = None
        if len(actions) > self.max_actions:
            keys = list(actions)
            pages = [keys[index:index + self.max_actions]
                     for index in range(0, len(keys), self.max_actions)]
            page_actions = {}
            for index, members in enumerate(pages):
                previews = []
                for key in members[:6]:
                    spec = actions[key]
                    description = spec.get('description', '') if isinstance(spec, dict) else str(spec)
                    previews.append(f'{key}: {description[:120]}')
                page_actions[f'group:{index}'] = {
                    'description': 'Candidate group containing: ' + '; '.join(previews),
                    'risk': 'compute',
                }
            page_query = {'candidate_group': choice(
                'Select the candidate group most likely to contain the next action. '
                'This is routing only and grants no permission.', page_actions)}
            router = self._load()
            page_started = time.monotonic()
            with self._lock:
                page_response = router.predict(state, page_query, model=self.model)
            page_raw = page_response.get('answers', {}).get('candidate_group')
            page_key, page_confidence, _ = self._decode(page_raw, page_actions)
            actions = {key: original_actions[key] for key in pages[int(page_key.split(':')[1])]}
            page_evidence = {'group': page_key, 'seconds': time.monotonic() - page_started,
                             'candidate_count': len(original_actions)}
        query = dict(questions or {})
        query[decision_key] = choice(instructions, actions)
        router = self._load()
        started = time.monotonic()
        with self._lock:
            response = router.predict(state, query, model=self.model)
        elapsed = time.monotonic() - started
        raw_answers = response.get('answers') if isinstance(response, dict) else None
        if not isinstance(raw_answers, dict):
            raise ValueError('Laya response has no answers object')
        raw = raw_answers.get(decision_key)
        action, confidence, distribution = self._decode(raw, actions)
        confidence = min(confidence, page_confidence)
        answers = {}
        for key, question in query.items():
            candidate = raw_answers.get(key)
            if isinstance(question, dict) and question.get('type') == 'choice':
                value, _, _ = self._decode(candidate, question.get('criteria', {}))
                answers[key] = value
            else:
                answers[key] = candidate
        routing = response.get('routing', {}) if isinstance(response, dict) else {}
        self.last = {'provider': 'laya', 'model': self.model, 'seconds': elapsed,
                     'routing': routing, 'usage': response.get('usage'),
                     'hierarchical_routing': page_evidence}
        return Decision(action=action, confidence=confidence, distribution=distribution,
                        answers=answers)
