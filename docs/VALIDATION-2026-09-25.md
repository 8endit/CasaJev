# Validation snapshot — 25 September 2026

CasaJev is an experimental local prototype. These results cover bounded CSV tool reuse and connector contract checks; they do not establish general reliability, production readiness, or superiority to a simple router.

The original comparison froze 12 valid CSV tasks, four rejection/clarification cases, expected results, and scoring before model runs. Each of three arms ran every case three times with fresh state (48 attempts per arm, 144 total) on runtime `8df9006`:

| Arm | Fully passed | Valid outputs | Rejection/clarification |
| --- | ---: | ---: | ---: |
| CasaJev, prepared tool | 36/48 | 30/36 | 6/12 |
| Deterministic router, same tool | 39/48 | 30/36 | 9/12 |
| CasaJev, empty tool library | 33/48 | 30/36 | 3/12 |

The original product gate **failed**. Median task times, including early failures, were 2.15 s, 0.28 s, and 32.76 s respectively; preparation and tool checks were excluded, and monetary cost was not measured. Prepared-tool reuse was checked by tool ID, source and contract hashes, and binding of unchanged CSV input. It did not demonstrate an autonomously accumulated tool library.

The failures led to narrower provider state, explicit domain rejection, bounded clarification, and early rejection of ambiguous named CSV headers. On intermediate commit `1124dc0`, a separate 25-attempt follow-up passed 15/16 known regressions and 7/9 new synthetic attempts. All 16 valid attempts reused the exact same prepared tool and matched independently fixed expected results. Three duplicate-header cases still failed. On `ddc169d`, a **separate narrow** follow-up passed those three cases and four preselected variants (7/7). The earlier 22/25 is not retroactively a pass for the final version. The full three-arm comparison was not rerun after the fixes.

Connector checks used local MCP processes and deterministic decisions. Following fixes to input/output schema binding, catalogue refresh, and response validation, 27/27 boundary checks across nine new variants passed. Six responses intentionally contained wrong values that remained **unverified** because they satisfied the schema. Contract checks cannot prove arbitrary output correctness.

Two unchanged public NOAA weekly exports produced 6/6 exact matches to independently retrieved JSON references across the three arms. They were examiner-selected public data, not customer tasks. CasaJev itself did not receive the external oracle, so its internal status remained `completed_unverified`. A deliberately plausible wrong CSV converter and four fixed external gold results remain in the repository as a regression check.

Offline regression checks for the affected behavior:

```sh
uv run --extra test pytest -q tests/test_acceptance_runtime.py tests/test_known_bad_converter_regression.py tests/test_connector_contract_drift.py
```

The integrated source at `ddc169d` passed 176/176 software tests locally on macOS. These tests and the small selected cases do not prove live reliability on other hosts or against arbitrary APIs. Live model replay may differ and incur provider costs.
