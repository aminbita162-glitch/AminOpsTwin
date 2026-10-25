# P14 Hard-Stop Report — Shadow Pilot Readiness, Claim Verification and Stage Close

## 1. PHASE

P14 — Shadow Pilot Readiness, Claim Verification and Stage Close

**P14-code tag hash (full):** `bfb4aa7b6ea8c905d81b0e930d811571f887421f`
**P14-code tag hash (short):** `bfb4aa7`

## 2. DONE

### Deliverables with file paths

1. **Sample Shadow Pilot Report (G14.1)**
   - `src/aminopstwin/shadow_pilot.py` — `ShadowPilotReport` model, `generate_shadow_pilot_report()` with deterministic hash, `save_shadow_pilot_report()`, `SHADOW_PILOT_SYNTHETIC_DATA` (8 rows of synthetic aggregate data satisfying Data Contract v1).
   - `test_home/P14/shadow_pilot_report.json` — generated report with calibration-style predicted-vs-actual comparison, metrics summary, deterministic report hash.
   - `tests/p14/test_shadow_pilot.py` — 15 tests (data contract compliance, required columns, synthetic labelling, generation, calibration comparison, metrics summary, deterministic hash, hash changes with different data, reproducible from file, stored under test_home/P14, file hash matches generated, valid JSON, no patient data, fixed timestamp, save to path).

2. **Final README Update (G14.2)**
   - `README.md` — P14 added to phase status table; "Stage 2 Complete (Candidate)" section added with [CLAIM-015] through [CLAIM-018] references.
   - `docs/claims.yaml` — 4 new claims added (CLAIM-015 through CLAIM-018), 18 total; existing README.md hashes updated for CLAIM-001, CLAIM-009, CLAIM-010.
   - `tests/p14/test_claims_resolve.py` — 5 tests (README has claim-ids, every README claim exists in registry, verify CLI all claims pass, verify CLI each README claim, tampered hash fails).

3. **Signed Tags (G14.3)**
   - Tags `P11-verified`, `P12-verified`, `P13-verified`, `P14-verified` created as lightweight tags (signing keys not yet rotated; directive permits lightweight tags).
   - `tests/p14/test_verified_tags.py` — 5 tests (all verified tags exist, P11/P12/P13/P14-verified individually).

4. **Full Regression (G14.4)**
   - `tests/p14/test_regression.py` — nested full-suite regression test with AMINOPS_REGRESSION_NESTED_P14 guard.
   - `test_home/P14/full_regression.txt` — full test suite output: 2549 passed, 0 failed.

5. **Release Notes (G14.4, DOC)**
   - `docs/release_notes_v0.2.0-candidate.md` — release notes for v0.2.0-candidate listing every P11–P14 capability with its real status, known limitations, and STATUS: CANDIDATE heading.

6. **Infrastructure**
   - `docs/gates.yaml` — G14.1–G14.4 added.
   - `scripts/check_commits.py` — G14.* added to GATE_IDS and PHASE_GATES["P14"].
   - `pyproject.toml` — `aminopstwin.shadow_pilot` added to mypy packages list.

### Commit count with capability/gate IDs

5 commits, all matching §21.3 regex:
- `3fe38a5` P14: add Shadow Pilot report with synthetic aggregate calibration data (G14.1)
- `b10cce7` P14: update README with Stage 2 Complete and add claim-id resolution tests (G14.2)
- `b20ed23` P14: add release notes for v0.2.0-candidate (G14.4, DOC)
- `9ded7b8` P14: add verified tags and full regression tests (G14.3, G14.4)
- `bfb4aa7` P14: add G14 gates, P14 phase gates, and infra updates (G14.1, G14.2, G14.3, G14.4, INFRA)

## 3. NOT DONE

- **Owner signing keys**: Tags P11-verified through P14-verified are lightweight tags, not cryptographically signed. The key rotation protocol (P13) is a skeleton with `[OWNER-FILL]` placeholders. Signing requires owner key material.
- **Real ClinicalTrials.gov/AACT data**: The Prior Pack remains SYNTHETIC. Real aggregate data requires owner-approved ingestion.

## 4. DEVIATIONS

- Two non-conforming commits (`f5344bd`, `9f3e77b`) with message "Update token_baseline.json" were pushed to origin/main by the owner/CI outside the P14 phase. These are timestamp churn from `test_home/P2/token_baseline.json` (a known issue documented in the skill). Per §21.2 (no history rewrite), these commits are left in place and noted as a deviation. The `P14-code` tag is placed on the last conforming P14 commit (`bfb4aa7`).

## 5. FAILED

No failing tests or gates.

## 6. MEASURED VALUES

| Gate | Description | Measured Value | Threshold | Pass? |
|------|-------------|----------------|-----------|-------|
| G14.1 | sample Shadow Pilot report exists and is reproducible | 15 passed | 1 (pass) | ✅ |
| G14.2 | all claim-ids in README resolve via verify CLI | 5 passed | 1 (pass) | ✅ |
| G14.3 | tags P11-verified through P14-verified exist | 5 passed | 1 (pass) | ✅ |
| G14.4 | full P1-P14 regression passes | 2549 passed, 0 failed | 1 (pass) | ✅ |
| — | Full regression (P1–P13 + P14, excluding nested) | 2549 passed, 0 failed | 0 failures | ✅ |
| — | mypy --strict (13 packages) | 0 errors, 61 source files | 0 | ✅ |
| — | ruff check (src/ + tests/) | All checks passed | 0 | ✅ |
| — | import-linter (Gateway purity) | 1 kept, 0 broken | 0 broken | ✅ |
| — | check_commits.py P14 | C2/C3/C4/C7 PASS (5 commits, 4 gates) | — | ✅ |
| — | aminopstwin-verify --all | 18 passed, 0 failed | 0 failed | ✅ |

## 7. OPEN QUESTIONS

No open questions for P14. (`grep -c '### OQ-P14' docs/open_questions.md` = 0)

## 8. README STATUS

README.md status panel updated: P14 shows `COMPLETE (CANDIDATE)`. "Stage 2 Complete (Candidate)" section added with [CLAIM-015] through [CLAIM-018] links.

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction.
