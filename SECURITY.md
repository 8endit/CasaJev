# Security policy

## Supported release

Security fixes are maintained for the latest published CasaJev release. The current
default deployment is a single-user local process bound to `127.0.0.1`; exposing the
HTTP server to a network or treating it as a multi-user service is unsupported.

## Reporting a vulnerability

Do not include credentials, private conversations, browser storage, or a weaponized
proof of concept in a public issue. If the repository is hosted on GitHub, use its
private security-advisory form. Otherwise contact the distributor privately and include
the affected version, reachable boundary, impact, and a minimal non-destructive
reproduction. Expect an acknowledgement within seven days.

## Security boundaries

- Laya and Jev may select only actions supplied by deterministic application code.
- A decision is not authorization. The host application must enforce permissions,
  actuator limits, deadlines, stale-state rejection, and a safe fallback.
- Generated Python tools run in macOS Seatbelt or in the constrained Docker worker on
  Windows/Linux. The container has no network, a read-only root, no capabilities,
  no-new-privileges and bounded resources. CasaJev has no unsandboxed fallback.
- Configured MCP servers are trusted local programs running with the user's authority;
  their `read_only` label is an explicit user grant, not an operating-system sandbox.
- The integrated public-web browser blocks loopback, link-local, private, reserved,
  and otherwise non-global destinations, including redirect requests.
- Local credentials and browser state are permission-restricted files, not encrypted
  vault entries. Protect the user account and disk accordingly.
- The HTTP interface is loopback-only and single-user. Host and Origin checks are a
  browser boundary, not authentication against other programs running as the user.

## Real-time safety

CasaJev provides soft real-time orchestration. A late, stale, invalid, or low-confidence
decision must resolve to the configured safe action and must never be executed later.
Do not use the model loop as the sole safety control for medical, vehicle, industrial,
life-safety, or other certified hard-real-time systems.
