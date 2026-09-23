# CasaJev 0.5.1 release evidence

Date: 2026-09-21

## Scope

- Separate, persisted decision providers for the general and real-time pipelines.
- First-run onboarding and later settings changes through the same validated API.
- Lazy Laya construction: selecting Laya does not download or load the model.
- macOS Seatbelt worker plus a Docker-isolated worker command for Windows/Linux.
- Existing SQLite state and the legacy `decision_provider` setting remain readable.

## Safety properties

- The UI only submits the two bounded provider identifiers `jev` and `laya`.
- A provider switch is rejected while work is queued or running.
- The general controller is atomically replaced after a validated settings write.
- The real-time factory reads its own provider, deadline and observation-age limits.
- No platform receives an unsandboxed dynamic-tool fallback.
- Docker workers have no network, a read-only root, no capabilities, no-new-privileges,
  a non-root user and explicit CPU, memory, process and output limits.

## Verification boundary

The full suite, package build, source/wheel install and live UI were exercised on macOS.
The Windows and Linux launchers and Docker command are included for external testing,
but were not represented as end-to-end verified on a real Windows or Linux host in this
release.
