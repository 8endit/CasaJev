"""Deadline-aware latest-value loop for bounded local decisions."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import queue
import threading
import time
from typing import Any, Callable, Mapping

from .contracts import digest


def from_settings(root, *, jev, safe_action='stop', clock=time.monotonic):
    """Build the configured embedded real-time path without loading Laya yet."""
    from .controller import DecisionController
    from .policies import decision_policy
    from .settings import settings
    options = settings(root)
    policy = decision_policy(options['realtime_decision_provider'], jev=jev,
                             laya_model=options['laya_model'])
    return RealtimeController(DecisionController(policy),
        deadline_ms=options['realtime_deadline_ms'], max_age_ms=options['realtime_max_age_ms'],
        safe_action=safe_action, clock=clock)


@dataclass
class RealtimeMetrics:
    submitted: int = 0
    decided: int = 0
    fallbacks: int = 0
    stale: int = 0
    deadline_misses: int = 0
    dropped: int = 0
    errors: int = 0
    latency_ms: deque = field(default_factory=lambda: deque(maxlen=512))

    def snapshot(self):
        ordered = sorted(self.latency_ms)
        percentile = lambda p: ordered[min(len(ordered) - 1, int((len(ordered) - 1) * p))] if ordered else None
        return {'submitted': self.submitted, 'decided': self.decided,
                'fallbacks': self.fallbacks, 'stale': self.stale,
                'deadline_misses': self.deadline_misses, 'dropped': self.dropped,
                'errors': self.errors, 'latency_ms_p50': percentile(.50),
                'latency_ms_p95': percentile(.95), 'latency_ms_max': max(ordered) if ordered else None}


class RealtimeController:
    """One bounded decision step; a missed deadline can never execute late."""

    def __init__(self, controller, *, deadline_ms: float = 500, max_age_ms: float = 250,
                 safe_action: str = 'stop', clock=time.monotonic):
        if deadline_ms <= 0 or max_age_ms <= 0:
            raise ValueError('Realtime deadlines must be positive')
        self.controller = controller
        self.deadline_ms, self.max_age_ms = float(deadline_ms), float(max_age_ms)
        self.safe_action, self.clock = safe_action, clock
        self.metrics = RealtimeMetrics()

    def step(self, *, observation: dict, actions: Mapping[str, Any], instructions: str,
             observed_at: float | None = None):
        started = self.clock()
        observed_at = started if observed_at is None else observed_at
        self.metrics.submitted += 1
        if self.safe_action not in actions:
            raise ValueError('The configured safe action is not available')
        age_ms = max(0.0, (started - observed_at) * 1000)
        if age_ms > self.max_age_ms:
            self.metrics.stale += 1
            self.metrics.fallbacks += 1
            return self._result(self.safe_action, 'stale_observation', age_ms, 0.0)
        try:
            decision, compiled = self.controller.choose(observation, actions, instructions)
        except Exception as exc:
            self.metrics.errors += 1
            self.metrics.fallbacks += 1
            elapsed = (self.clock() - started) * 1000
            return self._result(self.safe_action, 'policy_error', age_ms, elapsed,
                                error=type(exc).__name__)
        elapsed = (self.clock() - started) * 1000
        self.metrics.latency_ms.append(round(elapsed, 3))
        if elapsed > self.deadline_ms:
            self.metrics.deadline_misses += 1
            self.metrics.fallbacks += 1
            return self._result(self.safe_action, 'deadline_missed', age_ms, elapsed,
                                decision=decision, compiled=compiled)
        if not decision.accepted:
            self.metrics.fallbacks += 1
            return self._result(self.safe_action, decision.reason or 'rejected', age_ms, elapsed,
                                decision=decision, compiled=compiled)
        self.metrics.decided += 1
        return self._result(decision.action, 'accepted', age_ms, elapsed,
                            decision=decision, compiled=compiled)

    @staticmethod
    def _result(action, reason, age_ms, elapsed_ms, *, decision=None, compiled=None, error=None):
        result = {'action': action, 'reason': reason, 'observation_age_ms': round(age_ms, 3),
                  'latency_ms': round(elapsed_ms, 3)}
        if decision is not None:
            result.update(confidence=decision.confidence, threshold=decision.threshold,
                          distribution=decision.distribution)
        if compiled is not None:
            result['state_digest'] = digest(compiled)
        if error:
            result['error'] = error
        return result


class LatestValueSession:
    """Background session with a one-item queue; old frames are dropped, never accumulated."""

    def __init__(self, controller: RealtimeController, on_result: Callable[[dict], None]):
        self.controller, self.on_result = controller, on_result
        self._queue = queue.Queue(maxsize=1)
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, name='casajev-realtime', daemon=True)
        self._thread.start()

    def submit(self, *, observation, actions, instructions, observed_at=None):
        item = {'observation': observation, 'actions': actions, 'instructions': instructions,
                'observed_at': time.monotonic() if observed_at is None else observed_at}
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
                self.controller.metrics.dropped += 1
            except queue.Empty:
                pass
            self._queue.put_nowait(item)

    def _run(self):
        while not self._closed.is_set():
            try:
                item = self._queue.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                self.on_result(self.controller.step(**item))
            finally:
                self._queue.task_done()

    def close(self, timeout=2):
        self._closed.set()
        self._thread.join(timeout=timeout)
