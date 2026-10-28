# Owner Key Rotation & Co-Signature Protocol (Idea S5, P13, G13.5)

## Purpose

A minimal protocol for rotating the owner signing key and allowing an
optional co-signature on Hard-Stop reports. This reduces the single-person
bus factor without requiring full Shamir secret sharing in this stage.

## Key Rotation Protocol

### Key types

| Key ID | Purpose | Holder |
|--------|---------|--------|
| `OWNER_SIGNING_KEY` | Signs evidence packs, Hard-Stop reports, prior pack manifests | Owner (Amin Azimi) |
| `CO_SIGNER_KEY` | Optional co-signature on Hard-Stop reports | Designated co-signer (owner-appointed) |

### Rotation procedure

1. **Generate new key pair**: The owner generates a new signing key pair
   using a documented tool (e.g., `python -c "import secrets; print(secrets.token_hex(32))"`).

2. **Record rotation event**: Add an entry to `docs/key_rotation_log.yaml`
   with the following fields:
   - `rotation_id`: sequential identifier (ROT-001, ROT-002, ...)
   - `rotated_at`: ISO 8601 timestamp
   - `old_key_id`: the key being retired
   - `new_key_id`: the new key being activated
   - `reason`: reason for rotation (scheduled, compromise, personnel change)
   - `signed_by`: the owner's signature confirming the rotation

3. **Verify continuity**: The old key signs a "transfer of trust" statement
   that delegates all prior signed artifacts to the new key. This statement
   is stored in `docs/key_rotation_log.yaml`.

4. **Activate new key**: All new signatures use the new key. Old signatures
   remain valid via the transfer-of-trust chain.

5. **Retire old key**: The old key is securely destroyed after the transfer
   is verified. The retirement is recorded in the rotation log.

### Rotation frequency

- **Scheduled**: every 90 days (quarterly).
- **Emergency**: upon suspected compromise, within 24 hours.
- **Personnel**: when a key holder departs the project.

## Co-Signature Protocol

### Optional second signature

Hard-Stop reports may carry an optional `co_signature` field. The presence
or absence of this field does not break verification — the signature is
optional but verifiable when present.

### Co-signature structure

```yaml
co_signature:
  co_signer_id: "<identifier of the co-signer>"
  co_signer_key_id: "<key identifier used>"
  signed_at: "<ISO 8601 timestamp>"
  signature: "<HMAC-SHA256 or Ed25519 signature over the report hash>"
```

### Verification

1. Compute the SHA-256 hash of the Hard-Stop Report content (excluding
   the `co_signature` field itself).
2. If `co_signature` is present, verify the signature against the
   co-signer's public key.
3. If `co_signature` is absent, the report is still valid — the
   co-signature is optional.
4. A report with a `co_signature` field that fails verification is
   INVALID regardless of the primary signature.

### Co-signer appointment

1. The owner appoints a co-signer by recording an entry in
   `docs/co_signer_registry.yaml`.
2. The entry includes: `co_signer_id`, `public_key`, `appointed_at`,
   `appointed_by` (owner signature).
3. A co-signer can be revoked by the owner at any time; revocations are
   recorded in the same registry.

## Security properties

- **No single point of failure**: the co-signature provides redundancy.
- **No forced dependency**: the co-signature is optional, so a missing
  co-signer does not block the workflow.
- **Auditability**: all rotations and co-signatures are logged.
- **Non-repudiation**: signatures are cryptographic, not social.

## Implementation status (P13)

This is a **protocol skeleton** — the signing keys are placeholders
(`[OWNER-FILL]`) and the co-signer registry is not yet populated.
The key rotation log and co-signer registry files will be created
in P14 or by the owner. The test (`tests/evidence/test_cosignature.py`)
verifies that the co-signature field is optional and does not break
verification when present.
