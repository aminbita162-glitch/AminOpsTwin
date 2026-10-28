# Owner Decisions — ADR Index

This file is an index of the approved Architecture Decision Records
(ADRs) in `docs/adr/`. Each ADR records a binding owner decision with
its context, decision, consequences, and proof tests.

| ADR | Title | Status | File |
|-----|-------|--------|------|
| ADR-001 | Hash-locked lockfile (uv.lock) | Accepted | `docs/adr/ADR-001-lockfile.md` |
| ADR-002 | Licence — comprehensive reservation of rights | Accepted | `docs/adr/ADR-002-licence.md` |
| ADR-003 | Revocation — epoch-based, fail-closed at the commit boundary | Accepted | `docs/adr/ADR-003-revocation.md` |
| ADR-004 | Idempotency — caller-supplied key plus payload fingerprint | Accepted | `docs/adr/ADR-004-idempotency.md` |
| ADR-005 | Audit anchoring — Merkle batches, signatures, qualified timestamps | Accepted | `docs/adr/ADR-005-audit-anchoring.md` |
| ADR-006 | UNKNOWN outcomes — explicit state, reconciliation, escalation | Accepted | `docs/adr/ADR-006-unknown-outcomes.md` |
| ADR-007 | Authority precedence — fixed hierarchy, deny-overrides | Accepted | `docs/adr/ADR-007-authority-precedence.md` |
| ADR-008 | Sovereign-by-design — jurisdiction as configuration | Accepted | `docs/adr/ADR-008-sovereign-by-design.md` |

## Superseded decisions

- **OD07 Stack selection**: superseded by the Stack Lock (§6.2). The
  agent never selects technology.
