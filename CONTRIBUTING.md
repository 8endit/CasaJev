# Contributing

Use Python 3.11 and keep generated data, credentials, SQLite state, and model caches out
of commits.

```sh
uv sync --python 3.11 --extra local --extra test
uv run --extra test pytest -q
```

Every decision-provider change needs contract tests for invalid output, bounded action
spaces, confidence gating, and deterministic safe fallback. Real-time changes also need
tests for stale observations, missed deadlines, and backpressure. Never loosen the
macOS worker sandbox or add a network-exposed server mode as a convenience fallback.
