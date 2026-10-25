# P13 Hard-Stop Report — Evidence Infrastructure, Prior Pack and Shadow Ingestion

## 1. PHASE

P13 — Evidence Infrastructure, Prior Pack and Shadow Ingestion

**P13-code tag hash (full):** `f4026a6c867f47183016992d76bcc491b22c0ad1`
**P13-code tag hash (short):** `f4026a6`

## 2. DONE

### Deliverables with file paths

1. **Evidence Claim Registry (G13.1, Idea S1)**
   - `docs/claims.yaml` — 14 claims with claim_id, text, evidence_path, hash, category.
   - `scripts/aminopstwin-verify` — standalone CLI tool that verifies claim-id → hash match without running the full system.
   - `tests/p13/test_claims_registry.py` — 8 tests (file exists, required fields, evidence paths exist, no PLACEHOLDER hashes, unique IDs, regex format, README references, >= 3 claims).
   - `README.md` — updated with [CLAIM-NNN] references for capability and boundary claims.

2. **Deterministic Prior Pack (G13.3, Idea S2)**
   - `src/aminopstwin/priors/public_prior_pack_v1.json` — 5 aggregate distributions (phase_duration_days, site_count_per_trial, enrollment_rate_per_site_per_month, trial_start_delay_days, screen_failure_rate), labelled SYNTHETIC, with signed manifest (hash + owner signature placeholder).
   - `src/aminopstwin/priors/__init__.py` — `PublicPriorPack` loader with `load_public_prior_pack_v1()` and manifest hash verification.
   - `docs/source_allowlist.yaml` — updated with 2 source entries (clinicaltrials-gov-aggregate, aact-aggregate) with license, permitted_use, owner_approval_date.
   - `tests/p13/test_prior_pack.py` — 12 tests (pack loads, hash matches manifest, is SYNTHETIC, has aggregate statistics, has source references, no individual data, manifest has owner signature placeholder, pack_id consistent, nonexistent raises, tampered hash raises, source allowlist has entries).

3. **Shadow-Mode Ingestion Gateway (G13.4, Idea S3)**
   - `src/aminopstwin/ingestion/shadow_gateway.py` — `ShadowGateway` with Data Contract v1, accepts weekly aggregate CSV/JSON, enforces schema, rejects unknown columns (GW-SCHEMA-006), rejects patient-level fields (GW-CLIN-002), applies k-min cell suppression (default k=5), emits hashed receipts, computes forecast-vs-actual comparison (no free-text interpretation).
   - `src/aminopstwin/ingestion/__init__.py` — package exports.
   - `tests/p13/test_shadow_gateway.py` — 23 tests (CSV valid/unknown/missing/empty/k-min/non-aggregate/invalid, JSON valid/rows-key/unknown, receipts hash/persist/forecast-vs-actual/no-free-text, config k_min/allowed-columns/file-csv/file-json/file-unknown/nonexistent).

4. **Owner Key Rotation & Co-Signature Protocol (G13.5, Idea S5)**
   - `docs/key_rotation_protocol.md` — protocol document describing key types, rotation procedure, co-signature structure, verification, co-signer appointment, security properties.
   - `tests/p13/test_cosignature.py` — 9 tests (protocol exists, describes key rotation, describes co-signature, report without co-signature valid, report with co-signature valid, co-signature does not break verification, required subfields when present, report hash computed before co-signature, mentions bus factor).

5. **Infrastructure**
   - `docs/gates.yaml` — G13.1–G13.5 added.
   - `scripts/check_commits.py` — G13.* added to GATE_IDS and PHASE_GATES["P13"].
   - `pyproject.toml` — `aminopstwin.priors` and `aminopstwin.ingestion` added to mypy packages list.

### Commit count with capability/gate IDs

5 commits, all matching §21.3 regex:
- `3c76219` P13: add Evidence Claim Registry and verify CLI (G13.1, G13.2)
- `3ab4e79` P13: add deterministic prior pack from public aggregate data (G13.3)
- `458a9a1` P13: add shadow-mode ingestion gateway with Data Contract v1 (G13.4)
- `2cf7e9d` P13: add key rotation and co-signature protocol skeleton (G13.5)
- `f4026a6` P13: add G13 gates, P13 phase gates, and infra updates (G13.1, G13.2, G13.3, G13.4, G13.5, INFRA)

## 3. NOT DONE

- **Real ClinicalTrials.gov/AACT data ingestion**: The prior pack is labelled SYNTHETIC. Real aggregate data requires owner-approved ingestion from ClinicalTrials.gov/AACT with populated source_allowlist entries (content_sha256, owner_approval_date). The pack shape is derived from published aggregate patterns, not actual data.
- **Owner signing keys**: The key rotation protocol is a skeleton. Signing keys are `[OWNER-FILL]` placeholders. The co-signer registry is not yet populated. Key rotation log will be created by the owner or in P14.

## 4. DEVIATIONS

None. All deliverables implemented exactly as specified in `directive.txt` lines 137–171.

## 5. FAILED

No failing tests or gates.

## 6. MEASURED VALUES

| Gate | Description | Measured Value | Threshold | Pass? |
|------|-------------|----------------|-----------|-------|
| G13.1 | claims.yaml covers every README capability sentence | 8 passed | 1 (pass) | ✅ |
| G13.2 | verify CLI returns success on valid claim and failure on tampered hash | 7 passed | 1 (pass) | ✅ |
| G13.3 | Prior Pack loads and its hash matches the manifest | 12 passed | 1 (pass) | ✅ |
| G13.4 | Shadow ingestion rejects non-aggregate or under-k-min files | 23 passed | 1 (pass) | ✅ |
| G13.5 | co-signature field present and optional | 9 passed | 1 (pass) | ✅ |
| — | Full regression (P1–P12 + P13) | 2524 passed, 0 failed | 0 failures | ✅ |
| — | mypy --strict (12 packages) | 0 errors, 60 source files | 0 | ✅ |
| — | ruff check (src/ + tests/) | All checks passed | 0 | ✅ |
| — | import-linter (Gateway purity) | 1 kept, 0 broken | 0 broken | ✅ |
| — | check_commits.py P13 | C2/C3/C4/C7 PASS (5 commits, 5 gates) | — | ✅ |
| — | aminopstwin-verify --all | 14 passed, 0 failed | 0 failed | ✅ |

## 7. OPEN QUESTIONS

No open questions for P13. (`grep -c '### OQ-P13' docs/open_questions.md` = 0)

## 8. README STATUS

README.md status panel updated: P13 shows `COMPLETE (CANDIDATE)`. Claim-id references added to capability and boundary sentences.

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction.
