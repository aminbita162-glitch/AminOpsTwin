# ADR-008: Sovereign-by-design — jurisdiction as configuration

## Status

Accepted

## Context

The system must support data sovereignty, multi-jurisdiction
deployment, and per-tenant policy control. LLM access must be
controllable per tenant, including a zero-LLM mode. Data classification
and residency must be enforced by the policy engine.

## Decision

Eight pillars:

1. Every datum carries a data-classification label. Patient-level data
   is a prohibited class.
2. Data residency is a per-tenant policy, enforced by the policy engine.
   LLM routing obeys it.
3. Cell-based regional deployment, with no cross-cell data flow. The
   global control plane holds metadata only.
4. One artifact, four deployment modes: shared SaaS, dedicated SaaS,
   customer cloud, on-premises or air-gapped.
5. A per-tenant model policy, including "no external LLM", backed by a
   complete deterministic zero-LLM mode.
6. Customer-managed keys (BYOK/HYOK), envelope encryption with an
   in-region HSM, and crypto-shredding for deletion.
7. Cloud-agnostic infrastructure as code.
8. Compliance-as-code: a control registry mapped to tests and evidence.

LLM access has three layers behind one adapter:

- an in-region frontier model under a data processing agreement, with
  zero retention and no training on customer data;
- a sovereign open-weight model;
- a small local router model.

Only aggregate operational data may reach any model. Prompts and
responses are hashed and recorded. Model versions are pinned.

## Consequences

- The LLM adapter port supports three layers and a per-tenant model
  policy.
- A zero-LLM mode works end to end.
- Data classification labels are carried on every datum.
- Prompts and responses are hashed and recorded.

## Proof tests

- `tests/tokens/test_llm_adapter.py` — the zero-LLM mode works end to
  end.
- `tests/contracts/test_envelope.py` — data-classification labels are
  carried on the payload.
