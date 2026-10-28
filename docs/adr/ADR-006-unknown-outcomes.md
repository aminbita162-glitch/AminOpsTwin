# ADR-006: UNKNOWN outcomes — explicit state, reconciliation, escalation

## Status

Accepted

## Context

An operation whose outcome is uncertain must never be treated as a
success, and it must never be blindly retried. The system must
deterministically resolve the uncertainty or escalate to a human
operator. Dependent workflows must be blocked until resolution.

## Decision

An operation whose outcome is uncertain enters `UNKNOWN`. It is never
treated as a success, and it is never blindly retried. A reconciler
resolves it against the transactional outbox and the effect ids
(ADR-004): if the effect is found, the state becomes `COMMITTED`; if
not, it becomes `FAILED`, and a retry with the same key is safe.

Backoff continues for at most 15 minutes. After that the state is
`ESCALATED` and the case goes to a human operator. Dependent workflows
are blocked until resolution. `UNKNOWN` is visible on the dashboard,
audited, and tracked by an SLO.

Assurance levels:

- **L1**: a TLA+ specification of the executor, model-checked in CI for
  no double effect, no lost effect, and eventual resolution.
- **L2**: a deterministic seeded fault-injection harness (a crash at
  every step boundary, partitions, clock skew), reproducible by seed,
  with a linearizability check of the effect log.
- **L3**: the outbox receipt is written in the same transaction as the
  effect; cause codes `GW-UNK-001` and upward, each with a runbook; error
  budget of UNKNOWN at most 0.1% and p99 resolution at most 15 minutes;
  manual resolution requires four eyes and is audited and anchored.

## Consequences

- The executor gains an `ESCALATED` state and its valid transitions.
- `GW-UNK-001` through `GW-UNK-005` cause codes are registered.
- The reconciler itself is built in P27.

## Proof tests

- `tests/executor/test_unknown_escalation.py` — `UNKNOWN` transitions
  to `ESCALATED` after backoff.
- `tests/contracts/test_reason_codes.py` — `GW-UNK-001` to `GW-UNK-005`
  are registered.
