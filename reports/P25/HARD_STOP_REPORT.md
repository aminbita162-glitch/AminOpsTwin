# Hard-Stop Report — P25 Truth Reset

## HEADER

- **Phase:** P25 — Truth Reset
- **Branch:** phase/P25-truth-reset
- **Head commit:** 3d031fe
- **Date (UTC):** 2026-10-28T13:09:14Z
- **Tool versions:** Python 3.12.13, ruff 0.17.2, mypy 1.20.2, import-linter 2.15, uv 0.12.2, deptry 0.25.1, pip-audit 2.10.1
- **CI run:** https://github.com/aminbita162-glitch/AminOpsTwin/actions/runs/40692282466
- **PR:** https://github.com/aminbita162-glitch/AminOpsTwin/pull/11

## RESULT

IMPLEMENTED (CANDIDATE) — all 11 CI checks green on PR 11.

## GATES

| Gate ID | Command | Result | Evidence |
|---------|---------|--------|----------|
| G25.1 | `pytest tests/governance -q` | PASS | reports/P25/evidence/G25.1.txt |
| G25.2 | `uv run deptry src` | PASS (0 findings) | CI: deptry job, success |
| G25.3 | `uv run mypy` | PASS (0 errors, 93 files) | CI: mypy job, success |
| G25.4 | `python scripts/check_skips.py` | PASS (14 skips, all approved) | CI: skips job, success |
| G25.5 | `pytest tests/governance/test_claim_guard.py -q` | PASS | reports/P25/evidence/G25.5.txt |
| G25.6 | CI matrix 3.12 and 3.13 on x86_64 and arm64 | ALL GREEN (11/11 checks) | CI run 40692282466 |
| G25.7 | `pytest tests/docs -q` | PASS | reports/P25/evidence/G25.7.txt |
| G25.8 | `python scripts/check_commits.py P25` | PASS (18 commits, 0 violations) | inline |
| S1 | `ruff check src/aminopstwin tests/` | PASS (0 findings) | CI: lint job, success |
| S2 | `mypy --strict` | PASS (0 errors, 93 files) | CI: types job, success |
| S3 | `lint-imports` | PASS (2 contracts kept) | CI: arch job, success |
| S4 | `pytest` (3133 passed, 11 skipped, 0 failed) | PASS | CI: all 4 test matrix jobs, success |
| S5 | Charter clause 17 thresholds | Met (coverage, mypy, ruff, import-linter) | inline |
| S6 | `gitleaks detect` + `pip-audit` | PASS (0 findings; "No known vulnerabilities found") | CI: security job, success |
| S7 | README and docs describe code exactly | PASS (claim guard verifies) | G25.5 |

## CHANGES

### Files modified (this session — stale path fix)

- `.github/workflows/ci.yml` — changed 3 `tests/p16/` references to `tests/twin/`
- `docs/gates.yaml` — updated 84 lines: all `tests/p4/`–`tests/p24/` source_command paths to domain-based layout
- `docs/regulatory_scope/applicability_matrix.yaml` — 14 boundary_tests paths updated
- `docs/formal/gateway_properties.md` — 3 test evidence paths updated (p18, p19)
- `docs/key_rotation_protocol.md` — 1 path updated (p13)
- `docs/integration/preservation_mapping.yaml` — 12 source_command paths updated (p4, p5)
- `docs/release_notes.md` — 5 test path references updated (p8, p9, p10)
- `tests/enterprise/test_assurance_pack.py` — 2 evidence_path fields (p18 → enterprise)
- `tests/enterprise/test_regression_p8.py` — 1 docstring path (p8 → enterprise)
- `tests/integration/test_regression_p9.py` — 2 docstring paths (p9 → integration, p8 → enterprise)
- `tests/governance/test_regression_p10.py` — 2 docstring paths (p10 → governance) + line-length fix
- `tests/api/test_multi_version_priors.py` — 2 evidence_path fields (p19 → api)

### Files modified (prior P25 sessions — summary)

See prior commits on this branch for the full list of added, moved, and modified files from deliverables 1–12. Key additions: `docs/status_model.md`, `docs/claims_map.yaml`, `docs/regulatory/intended_purpose.md`, `tests/governance/test_directive_format.py`, `tests/governance/test_check_commits.py`, `tests/governance/test_claim_guard.py`, `src/aminopstwin/py.typed`. Key moves: 82 test files from `tests/p4/`–`tests/p24/` to domain folders via `git mv`.

## FINDINGS

### Deviations

1. **Stale test paths in CI and docs**: After deliverable 6 moved `tests/p4/`–`tests/p24/` to domain folders, 272 references to the old paths remained in `.github/workflows/ci.yml`, `docs/gates.yaml`, `docs/regulatory_scope/applicability_matrix.yaml`, `docs/formal/gateway_properties.md`, `docs/key_rotation_protocol.md`, `docs/integration/preservation_mapping.yaml`, `docs/release_notes.md`, and 5 test files. Fixed in commit `3d031fe` (this session). The CI workflow's three `tests/p16/` references were the direct cause of the ubuntu 3.13 test job failure in the prior CI run.

2. **Nested regression timeout**: The `tests/enterprise/test_regression_p8.py` test times out at 300s when run locally without the `AMINOPS_REGRESSION_NESTED=1` environment variable (it spawns a subprocess running the full suite). This is a pre-existing design issue; CI sets the env vars and the test passes there. The local full suite passes with the CI env vars set (3133 passed, 11 skipped, 0 failed in 222s).

3. **Historical evidence in test_home/**: `test_home/P<n>/HARD_STOP_REPORT.md` files contain old `tests/p<n>/` paths. These are frozen historical records from prior phases, outside ALLOWED PATHS for P25, and were not modified.

### CVEs

pip-audit reported **0 CVEs** — "No known vulnerabilities found."

### Gaps

- G26.1 (OWNER-FILL elimination) is not addressed in P25 — the directive assigns it to P26. The `docs/owner_decisions.md` OWNER-FILL markers remain by design.

## PROPOSALS

1. **Increase regression test timeout**: The 300s timeout in `test_regression_p8.py` is marginal for local runs. Consider raising it to 600s or adding a `pytest.ini` timeout marker. (P28 scope — CI hardening.)

2. **Automate stale-path detection**: Add a CI check that greps for `tests/p\d+/` references outside `test_home/` and `docs/archive/` to prevent stale paths from recurring. (P28 scope.)

## OWNER

1. Merge `phase/P25-truth-reset` into `main` after review.
2. After merge, proceed to P26 (Owner Decisions as ADRs and Core Semantics).
