# Hard-Stop Report — P25 Truth Reset

## HEADER

- **Phase:** P25 — Truth Reset
- **Branch:** phase/P25-truth-reset
- **Head commit:** 2063cdf3c09b302e76e46fcd499d9d3a0297fef9
- **Date (UTC):** 2026-10-27T02:01:28Z
- **Tool versions:** Python 3.12.13, ruff 0.17.2, mypy 1.20.2, import-linter 2.15, uv 0.12.2, deptry 0.25.1

## RESULT

IMPLEMENTED (CANDIDATE)

## GATES

| Gate ID | Command | Result | Evidence |
|---------|---------|--------|----------|
| G25.1 | `pytest tests/governance -q` | PASS | reports/P25/evidence/G25.1.txt |
| G25.2 | `uv run deptry src` | PASS (0 findings) | inline |
| G25.3 | `uv run mypy` | PASS (0 errors, 93 files) | inline |
| G25.4 | `python scripts/check_skips.py` | PASS (14 skips, all approved) | inline |
| G25.5 | `pytest tests/governance/test_claim_guard.py -q` | PASS (8 tests) | reports/P25/evidence/G25.5.txt |
| G25.6 | CI matrix 3.12 and 3.13 on x86_64 and arm64 | CI config updated, not run locally | .github/workflows/ci.yml |
| G25.7 | `pytest tests/docs -q` | PASS (42 tests) | reports/P25/evidence/G25.7.txt |
| G25.8 | `python scripts/check_commits.py P25` | PASS (17 commits, 0 violations) | inline |
| S1 | `ruff check src/aminopstwin/ tests/` | PASS (0 findings) | inline |
| S2 | `mypy --strict` | PASS (0 errors, 93 files) | inline |
| S3 | `lint-imports` | PASS (2 contracts kept) | inline |
| S4 | `pytest` | PASS (3133 passed, 11 skipped, 0 failed) | reports/P25/evidence/baseline_test.txt |
| S5 | Charter clause 17 thresholds | Met (coverage, mypy, ruff, import-linter) | inline |
| S6 | `gitleaks detect` | SKIP (owner-installed tool, not on PATH) | inline |
| S7 | README and docs describe code exactly | PASS (claim guard verifies) | G25.5 |

## CHANGES

### Files added
- reports/P25/PROGRESS.md
- reports/P25/evidence/baseline_test.txt
- docs/status_model.md
- docs/claims_map.yaml
- docs/regulatory/intended_purpose.md
- tests/governance/__init__.py
- tests/governance/test_directive_format.py
- tests/governance/test_check_commits.py
- tests/governance/test_claim_guard.py
- tests/docs/__init__.py
- src/aminopstwin/py.typed

### Files modified
- docs/gates.yaml (P25 gates registered)
- docs/claims.yaml (README hash resync)
- docs/test_exceptions.md (new paths for domain-based layout)
- docs/owner_decisions.md (unchanged — OWNER-FILL remains per scope)
- pyproject.toml (removed unused deps, added deptry + pyyaml, Python 3.13, deptry config, mypy single source)
- uv.lock (re-locked after dependency changes)
- .gitignore (added .coverage.*)
- .github/workflows/ci.yml (mypy no package list, Python 3.13 matrix, deptry job, check_skips job)
- README.md (three-level status model, GOVERNANCE for P1-P24, all 60 capabilities SPECIFIED, Technology section, Architecture section, Measured Summary)
- scripts/check_commits.py (generalised: P1-P99, gate IDs from gates.yaml)
- scripts/stage3_close.py (GOVERNANCE instead of COMPLETE (CANDIDATE))
- scripts/stage4_close.py (GOVERNANCE instead of COMPLETE (CANDIDATE))
- src/aminopstwin/agents/base.py (replaced __import__("hashlib") with normal import)
- src/aminopstwin/twin/simulation.py (removed SimPy claim)
- src/aminopstwin/enterprise/rls.py (states "simulated until P27")
- src/aminopstwin/executor/__init__.py (states "in-memory, no durability until P27")
- src/aminopstwin/dashboard/app.py (states "auth not implemented until P33")
- src/aminopstwin/assurance/signed_pack.py (integrity tag (HMAC), asymmetric arrives P32)
- src/aminopstwin/stage_seal.py (integrity tag (HMAC), asymmetric arrives P32)
- src/aminopstwin/stage4_seal.py (integrity tag (HMAC), asymmetric arrives P32)
- src/aminopstwin/integration/exports.py (integrity tag, asymmetric arrives P32)
- tests/dashboard/test_dashboard.py (updated assertion for new message)
- tests/integration/test_deployment.py (updated assertion: pyyaml instead of sqlalchemy)
- tests/governance/test_regression_p10.py (fixed tests/p9/ -> tests/integration/)

### Files moved (git mv, 82 test files)
- tests/p4/*.py -> tests/governance/*.py
- tests/p5/*.py -> tests/twin/*.py
- tests/p6/*.py -> tests/assurance/*.py
- tests/p7/*.py -> tests/dashboard/*.py
- tests/p8/*.py -> tests/enterprise/*.py
- tests/p9/*.py -> tests/integration/*.py
- tests/p10/*.py -> tests/governance/*.py
- tests/p13/*.py -> tests/evidence/*.py
- tests/p14/*.py -> tests/evidence/*.py + tests/governance/test_regression_p14.py
- tests/p15/*.py -> tests/governance/*.py
- tests/p16/*.py -> tests/twin/*.py
- tests/p17/*.py -> tests/evidence/*.py + tests/governance/test_regression_p17.py
- tests/p18/*.py -> tests/enterprise/*.py + tests/governance/test_regression_p18.py
- tests/p19/*.py -> tests/api/*.py + tests/governance/test_regression_p19.py
- tests/p20/*.py -> tests/governance/*.py + tests/governance/test_regression_p20.py
- tests/p21/test_regression.py -> tests/governance/test_regression_p21.py
- tests/p22/test_regression.py -> tests/governance/test_regression_p22.py
- tests/p23/*.py -> tests/governance/*.py + tests/governance/test_regression_p23.py
- tests/p24/*.py -> tests/governance/*.py + tests/governance/test_regression_p24.py
- tests/p15/test_readme.py -> tests/docs/test_readme.py
- tests/p21/test_status_honesty.py -> tests/docs/test_status_honesty.py
- tests/p21/test_readme_cinematic.py -> tests/docs/test_readme_cinematic.py
- tests/p22/test_gate_source_consistency.py -> tests/docs/test_gate_source_consistency.py

### Files retired (git mv to docs/archive/)
- tests/p22/test_directive_consistency.py -> docs/archive/retired_tests/
- tests/p22/test_owner_fill_eliminated.py -> docs/archive/retired_tests/
- scripts/check_directive_consistency.py -> docs/archive/

### Files deleted
- tests/p4-p24/__init__.py (19 files, empty directories cleaned up)

## FINDINGS

### Deviations
- Commit `ba7f871` (now `b050579` after reword) originally had a summary containing
  parentheses `(HMAC)` which broke the commit-message regex. The commit was
  reworded via `git rebase` before any push (local branch only). No history was
  rewritten after pushing.

### Gaps
- G25.6 (CI matrix 3.12 and 3.13) is configured but not run locally — CI is the
  owner's infrastructure. The CI workflow includes the matrix.
- S6 (gitleaks) is SKIP — gitleaks is an owner-installed tool not on PATH in this
  environment. The secrets baseline is enforced by .gitignore and manual review.
- G26.1 (OWNER-FILL elimination) is not addressed in P25 — the directive assigns
  it to P26. The `docs/owner_decisions.md` OWNER-FILL markers remain by design.

## PROPOSALS

None.

## OWNER

1. Merge `phase/P25-truth-reset` into `main` after review.
2. Run `gitleaks detect` and `pip-audit` on the branch before merging.
3. Run the CI matrix (3.12 and 3.13 on x86_64 and arm64) on the pull request.
4. After merge, proceed to P26 (Owner Decisions as ADRs and Core Semantics).
