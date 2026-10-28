# ADR-007: Authority precedence — fixed hierarchy, deny-overrides

## Status

Accepted

## Context

Authorization decisions must follow a fixed precedence hierarchy. A
conflict at the same level must resolve to DENY. LLM output must carry
zero authority. Break-glass must be controlled, time-limited, and
audited.

## Decision

There is a fixed hierarchy, highest level first:

1. Law and the non-medical invariants, hard-coded and never overridable.
2. Platform security.
3. Owner governance, as a signed policy bundle.
4. Tenant administration, which may only narrow.
5. Role and user permissions.
6. Agent requests; LLM output carries zero authority.

A conflict at the same level resolves to DENY (deny-overrides). There
is no implicit allow. Policy bundles are versioned, signed and bound to
an epoch. The winning rule id is logged with every decision.

Break-glass applies only to levels 3 to 6; it requires dual control,
lasts at most 4 hours, revokes itself automatically, is reviewed
afterwards, and is fully audited.

Assurance levels:

- **L1**: Cedar policy language.
- **L2**: SMT-based policy analysis in CI.
- **L3**: a signed policy supply chain with two-person approval for
  levels 2 and 3.
- **L4**: decision replay, plus a 30-day shadow evaluation of every new
  bundle before activation.
- **L5**: the Gateway is the sole decision point, with enforcement on
  every endpoint and every agent tool call, and short-lived,
  non-delegable capability tokens.

Implementation of L1, L2 and L5: P33.

## Consequences

- The six levels are represented as data in the domain layer.
- Deny-overrides combining is implemented in the Gateway.
- The winning rule id is logged in every DecisionRecord.

## Proof tests

- `tests/gateway/test_authority_precedence.py` — a lower-level ALLOW
  never flips a higher-level DENY; an equal-level conflict yields DENY.
- `tests/contracts/test_decision_record.py` — the winning rule id is
  logged in every DecisionRecord.
