# ADR-003: Revocation — epoch-based, fail-closed at the commit boundary

## Status

Accepted

## Context

Revocation must be deterministic, auditable, and fail-closed. A stale
revocation list must cause the system to deny rather than allow.
In-flight work that has been revoked must not produce committed effects.
Revocation must support multiple scopes (principal, key, capability,
tenant).

## Decision

Revocation is an audited event that increments `policy_epoch`. Envelopes
carrying a stale epoch are denied with `GW-REVOKE-001`. In-flight work is
re-authorised immediately before `COMMIT_INTENT`. If it is revoked, no
effect is written and the workflow enters `REVOKED`. Effects committed
earlier remain and are flagged in the audit trail.

There is no un-revoke: a re-grant is a new grant with a new id. A stale
revocation list makes the system fail closed.

Revocation scopes: principal, key, capability, tenant.

## Consequences

- The executor gains a `REVOKED` state with valid transitions from
  `CHECKPOINTED`.
- A re-authorisation hook runs immediately before `COMMIT_INTENT`.
- The `policy_epoch` increments on every revocation event.
- `GW-REVOKE-001` is registered as a reason code.

## Proof tests

- `tests/executor/test_revocation.py` — revocation between
  `CHECKPOINTED` and `COMMIT_INTENT` yields zero commits.
- `tests/contracts/test_reason_codes.py` — `GW-REVOKE-001` is
  registered.
