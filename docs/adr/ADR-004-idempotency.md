# ADR-004: Idempotency — caller-supplied key plus payload fingerprint

## Status

Accepted

## Context

Effectful operations must be exactly-once under retries and concurrent
duplicates. The idempotency key must come from the caller, never from an
agent or factory. Duplicate keys with different payloads must be
rejected. Duplicate keys while the first request is in progress must
return an in-progress response without a second execution.

## Decision

Every effectful operation requires an `Idempotency-Key` supplied by the
caller. A missing key is denied with `GW-IDEMP-001`. The key scope is
`(tenant, principal, key)`. The fingerprint is the canonical hash of the
payload.

- Same key, same fingerprint: the stored result is returned; nothing is
  executed again.
- Same key, different fingerprint: denied with `GW-IDEMP-002` (HTTP
  409).
- Duplicate while the first request is still in progress: an
  in-progress response is returned, with no second execution.

Keys live 7 days at the API layer. Committed effect ids are permanent.

## Consequences

- An `IdempotencyStore` port is defined in contracts.
- A thread-safe in-memory adapter provides the store.
- The Gateway and executor enforce ADR-004 exactly.
- `GW-IDEMP-001` and `GW-IDEMP-002` are registered as reason codes.

## Proof tests

- `tests/contracts/test_idempotency.py` — 100 concurrent requests with
  the same key produce exactly one effect.
- `tests/contracts/test_idempotency.py` — same key with a different
  payload is denied with `GW-IDEMP-002`.
