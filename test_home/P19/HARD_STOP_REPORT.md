# P19 Hard-Stop Report — Versioned Contracts, Cryptographic Outputs and API

## 1. PHASE + hash of last CODE commit (tag `P19-code`)

- **Phase:** P19 — Versioned Contracts, Cryptographic Outputs and API
- **P19-code tag:** `bbb4669` (full: `bbb46692a32b6f5c0136c9c8717d3b98ec7312bb`)

## 2. DONE: deliverables with file paths; commit count with capability/gate IDs

### Deliverables

| Deliverable | File Path | Gate |
|---|---|---|
| G19 gate IDs, phase gates, gates.yaml entries | `docs/gates.yaml`, `scripts/check_commits.py` | G19.1–G19.5, INFRA |
| Data Contract v2 (additive-only evolution, compatibility tests) | `src/aminopstwin/contracts/data_contract.py`, `tests/p19/test_data_contract.py` | G19.1 |
| Synthetic aggregate generator (SYNTHETIC labels) | `src/aminopstwin/fixtures_gen/synthetic_priors.py`, `tests/p19/test_synthetic_generator.py` | G19.1 |
| Signed export with co-signature field and offline verify tool | `src/aminopstwin/integration/exports.py`, `scripts/verify_export.py`, `tests/p19/test_signed_export.py` | G19.2 |
| Read-only aggregate API (RFC 9457 errors, Idempotency-Key) | `src/aminopstwin/api/__init__.py`, `tests/p19/test_api.py` | G19.3 |
| Public prior pack v2 JSON | `src/aminopstwin/priors/public_prior_pack_v2.json` | G19.1, G19.4 |
| Multi-version priors module (version hash in Evidence Pack) | `src/aminopstwin/priors/__init__.py`, `src/aminopstwin/assurance/signed_pack.py`, `tests/p19/test_multi_version_priors.py` | G19.4, G18.4 |
| Full regression test | `tests/p19/test_regression.py` | G19.5 |
| Full regression output | `test_home/P19/full_regression.txt` | G19.5 |
| README status table update (P19 → COMPLETE CANDIDATE) | `README.md` | DOC |
| Claims.yaml update (new CLAIM-019, README hash resync) | `docs/claims.yaml` | DOC |

### Commit count

9 P19 commits:
1. `da3be9a` — P19: add G19 gate IDs, phase gates, and gates.yaml entries (G19.1, G19.2, G19.3, G19.4, G19.5, INFRA)
2. `aa57c9e` — P19: add Data Contract v2 with additive-only evolution and compatibility tests (G19.1)
3. `11d5777` — P19: add synthetic aggregate generator matching prior shapes with SYNTHETIC labels (G19.1)
4. `a507ddf` — P19: add signed export with co-signature field and offline verify tool (G19.2)
5. `88d1eba` — P19: add read-only aggregate API with RFC 9457 errors and Idempotency-Key (G19.3)
6. `6dae40d` — P19: add public_prior_pack_v2.json with computed manifest hash (G19.4, G19.1)
7. `d55815d` — P19: add multi-version priors module with version hash in Evidence Pack (G19.4, G18.4)
8. `c63d211` — P19: add full regression test for G19.5 with nested guard propagation (G19.5, INFRA)
9. `bbb4669` — P19: update README status table, claims.yaml hashes, and full regression output (G19.1, G19.2, G19.3, G19.4, G19.5, DOC)

## 3. NOT DONE: every required item not completed

None. All P19 deliverables (G19.1–G19.5) are complete.

## 4. DEVIATIONS: any deviation from the directive

- `tests/p18/test_assurance_pack.py` was modified to update the expected file count from 4 to 5 (adding `prior_version.json` to the pack file list and existence check). This is a consequence of extending `SignedAssurancePack` with the `prior_version.json` file for G19.4. The P18 test still passes with the updated count.
- 10 Dependabot PRs (#1–#10) are open. All are deferred — see Section 11 for the rationale.

## 5. FAILED: every failing test or gate with output excerpt

None. All gates and tests pass.

## 6. MEASURED VALUES: each gate with the measured number

| Gate | Source Command | Measured Value |
|---|---|---|
| G19.1 | `pytest tests/p19/test_data_contract.py -v` | 22 passed |
| G19.2 | `pytest tests/p19/test_signed_export.py -v` | 16 passed |
| G19.3 | `pytest tests/p19/test_api.py -v` | 15 passed |
| G19.4 | `pytest tests/p19/test_multi_version_priors.py -v` | 31 passed |
| G19.5 | `pytest tests/p19/test_regression.py -v` | full regression: 2939 passed, 1 skipped, 0 failures |

### Quality gates

| Gate | Command | Result |
|---|---|---|
| mypy --strict | `mypy --strict --package aminopstwin.contracts ... --package aminopstwin.api` | Success: no issues found in 88 source files |
| ruff check | `ruff check src/aminopstwin/ tests/` | All checks passed |
| import-linter | `lint-imports` | 2 contracts kept, 0 broken |
| check_commits.py P19 | `python3 scripts/check_commits.py P19` | ALL COMMIT CHECKS PASS (8 commits, 5 gates referenced) |
| claims verify | `python scripts/aminopstwin-verify --all` | 19 passed, 0 failed |

## 7. OPEN QUESTIONS: pointers to docs/open_questions.md

No new open questions for P19.

## 8. README STATUS: confirmation that the status panel was updated

README.md status table updated: P19 row now shows `COMPLETE (CANDIDATE)`. P20 row shows `NOT STARTED`. The Hard-Stop Report link for P19 was added to the report list. The measured summary was updated to "2939 tests passed, 1 skipped, 0 failures (P19 regression)."

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction.

## 11. DEPENDABOT PRs — DEFERRED

The following 10 Dependabot PRs are open and deferred:

| PR | Title | Status | Reason for deferral |
|---|---|---|---|
| #10 | Update cyclonedx-bom ≥4.0.0,<8.0.0 | DEFERRED | Version-range widening only; no code changes; lockfile pins current version |
| #9 | Update fastapi ≥0.115.0,<0.160.0 | DEFERRED | Version-range widening only; no code changes; lockfile pins current version |
| #8 | Update schemathesis ≥3.36.0,<5.0.0 | DEFERRED | Version-range widening only; no code changes; lockfile pins current version |
| #7 | Update pytest-cov ≥5.0.0,<8.0.0 | DEFERRED | Version-range widening only; no code changes; lockfile pins current version |
| #6 | Update mutmut ≥2.5.0,<4.0.0 | DEFERRED | Version-range widening only; no code changes; lockfile pins current version |
| #5 | Bump actions/checkout 4.4.0 → 7.0.1 | DEFERRED | GitHub Actions version bump; CI actions are pinned by SHA; requires owner verification |
| #4 | Update mypy ≥1.11.0,<3.0.0 | DEFERRED | Version-range widening only; no code changes; lockfile pins current version |
| #3 | Bump actions/setup-python 5.6.0 → 7.1.0 | DEFERRED | GitHub Actions version bump; CI actions are pinned by SHA; requires owner verification |
| #2 | Update pytest ≥8.3.0,<10.0.0 | DEFERRED | Version-range widening only; no code changes; lockfile pins current version |
| #1 | Bump gitleaks/gitleaks-action | DEFERRED | GitHub Actions SHA bump; requires owner verification of the new SHA |

**Rationale:** All 10 PRs are Dependabot version-range widenings or GitHub Actions SHA bumps. None contain code changes to `src/` or `tests/`. Merging them would:
1. Create merge commits, violating the linear-history directive (§21.2).
2. Require re-running `uv lock` and updating the lockfile for the pip PRs.
3. Require owner verification of new GitHub Actions SHA pins for the action bumps.

These are safe to defer to the owner for evaluation outside the phase hard-stop.
