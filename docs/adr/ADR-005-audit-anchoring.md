# ADR-005: Audit anchoring — Merkle batches, signatures, qualified timestamps

## Status

Accepted

## Context

The audit trail must be tamper-evident and externally verifiable. An
internal hash chain is necessary but not sufficient: it must be anchored
to an external trust anchor via Merkle trees and RFC 3161 timestamps.
Audit storage must be write-once: no role may UPDATE or DELETE.

## Decision

The internal hash chain is kept. Every 15 minutes or every 1000 events,
whichever comes first, a Merkle tree is built. Its root is signed with
Ed25519 and timestamped under RFC 3161 by a configurable eIDAS-qualified
timestamp authority. An optional public transparency log may also be
used. Every event has an inclusion proof that can be verified offline.

Audit storage is write-once: no role may UPDATE or DELETE. If anchoring
lags by more than 1 hour, new commits are refused (fail closed). Only
identifiers and hashes are stored.

## Consequences

- The hash chain and Merkle batching are implemented in the evidence
  module.
- Signing and timestamping are implemented in P32.
- The audit storage is append-only with no UPDATE or DELETE.
- Anchoring lag above 1 hour causes new commits to be refused.

## Proof tests

- `tests/evidence/test_merkle_pack.py` — tampering and deletion are
  detected; receipts verify offline.
- Signing and timestamping proof: P32.
