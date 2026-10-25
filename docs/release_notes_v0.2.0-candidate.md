# Release Notes — v0.2.0-candidate

## STATUS: CANDIDATE

All capabilities remain Candidate until independently verified by
owner-approved evidence. No capability is marked as verified without a
passing evidence path.

## Stage 2 (P11–P14) — Candidate

### P11 — Spec Consolidation, Package Hygiene and CI Foundation

- Renamed package layout from `src/` to `src/aminopstwin/` with all
  imports, mypy, ruff, import-linter, and hatch paths updated.
- Added `uv.lock` hash-locked lockfile with CI check `uv lock --check`.
- Removed `.mutmut-cache` from git tracking; mutation results stored as
  JSON under `test_home/<phase>/mutation.json`.
- Created `.github/workflows/ci.yml` with jobs: lint, types, test,
  security, arch. All actions pinned by SHA. Permissions: `contents: read`.
- Documented the lockfile choice in `docs/adr/ADR-001-lockfile.md`.

**Status: COMPLETE (CANDIDATE)** — Gates G11.1–G11.5 pass.

### P12 — Core Determinism and Safety Hardening

- Raw JSON ingestion at API edge: rejects floats, NaN, Infinity, and
  duplicate keys with exact reason codes (`src/aminopstwin/gateway/raw_json.py`).
- Two IdFactory implementations: `DeterministicIdFactory` (HMAC-SHA256)
  and `EntropyIdFactory` (`secrets.token_bytes`); crash-safe `step_id`
  with no duplicate or orphan IDs after simulated crash.
- Closed TOCTOU for `policy_epoch` with atomic commit guard; zero commits
  with stale epoch.
- Explicit `StateFacts` snapshot passed to the pure Gateway function;
  `DecisionRecord` includes `hash(StateFacts)`.
- Integer-oriented simulation time (milliminutes) with named PRNG streams;
  `math.*` floating-point operations banned on the hashed state path.
- Cross-platform state hash oracle: final state hash identical on x86_64
  and ARM64 (`tests/twin/test_cross_platform_oracle.py`).

**Status: COMPLETE (CANDIDATE)** — Gates G12.1–G12.5 pass.

### P13 — Evidence Infrastructure, Prior Pack and Shadow Ingestion

- Evidence Claim Registry (`docs/claims.yaml`) with 14 claim-ids mapping
  to signed evidence-pack hashes. Standalone CLI `scripts/aminopstwin-verify`
  verifies any claim without running the full system.
- Deterministic Prior Pack from public ClinicalTrials.gov/AACT aggregate
  data (labelled SYNTHETIC); signed manifest with owner signature
  placeholder. Source allowlist documented in `docs/source_allowlist.yaml`.
- Shadow-mode ingestion gateway with Data Contract v1
  (`src/aminopstwin/ingestion/shadow_gateway.py`): accepts weekly
  aggregate CSV/JSON, enforces schema, rejects unknown columns, applies
  k-min cell suppression (default k=5), emits hashed receipts.
- Owner key rotation and co-signature protocol skeleton documented in
  `docs/key_rotation_protocol.md`; co-signature field is present and
  optional.

**Status: COMPLETE (CANDIDATE)** — Gates G13.1–G13.5 pass.

### P14 — Shadow Pilot Readiness, Claim Verification and Stage Close

- Sample Shadow Pilot report with synthetic aggregate data satisfying
  Data Contract v1; calibration-style comparison of predicted vs actual
  aggregate metrics; stored under `test_home/P14/shadow_pilot_report.json`.
- Final README update with "Stage 2 Complete (Candidate)" section and
  claim-id links.
- Signed tags P11-verified through P14-verified created.
- Full P1–P14 regression passes with 0 failures.
- Release notes for v0.2.0-candidate (this file).

**Status: COMPLETE (CANDIDATE)** — Gates G14.1–G14.4 pass.

## Stage 1 (P1–P10) — Candidate

All Stage 1 capabilities remain COMPLETE (CANDIDATE). See the phase
status table in `README.md` for the full list.

## Known Limitations

- The Prior Pack is labelled SYNTHETIC. Real aggregate data requires
  owner-approved ingestion from ClinicalTrials.gov/AACT public aggregates.
- Owner signing keys are `[OWNER-FILL]` placeholders. The key rotation
  protocol is a skeleton awaiting owner key material.
- No capability is claimed as verified without independent owner review.
- The system is not a medical device, not clinically validated, not
  production-ready, and not synchronized with a real organization.
