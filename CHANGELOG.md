# Changelog

## 0.5.1 — 2026-09-21

- Added an Electron macOS desktop app whose sandboxed `WebContentsView` is both the
  visible page and the browser surface controlled by CasaJev.
- Added a token-authenticated local desktop/browser bridge, blocked browser permissions,
  downloads, pop-ups and private-network requests, plus persistent desktop state.
- Bound ordinary model clicks to observed element indices; raw coordinates remain for
  canvases and other pixel-only targets.
- Added a general browser-action route with screenshot-grounded, typed command batches
  for clicking, typing, keys, scrolling and canvas pointer control.
- Added durable action clarifications so a short user answer resumes the original goal
  instead of being routed as a new chat request.
- Added first-run onboarding with separate providers for general and real-time pipelines.
- Made both provider choices editable at runtime without downloading Laya on selection.
- Added a settings-backed factory for embedded real-time controllers.
- Added Linux and Windows launchers plus an isolated Docker worker backend; no
  unsandboxed fallback is permitted.
- Preserved the 0.5.0 global-provider choice when migrating existing configuration.

## 0.5.0 — 2026-09-21

- Added an optional, revision-pinned local Laya decision provider.
- Added a deadline- and stale-state-aware latest-value soft real-time loop.
- Kept Jev as the default general router after a frozen comparison showed Laya was not
  an accurate drop-in replacement for the current German routing task.
- Added public/private network separation for the integrated browser.
- Pinned the Python and local-ML dependency set for Intel macOS reproducibility.
- Added Apache-2.0 licensing, security guidance, contribution guidance, model evidence,
  and release packaging metadata.

## 0.4.0 — 2026-09-21

- Added the replaceable bounded decision controller, state compiler, confidence gate,
  and shared fast loop.
