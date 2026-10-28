# P26 — Hard-Stop Report

## HEADER
- **Phase:** P26 — Owner Decisions as ADRs and Core Semantics
- **Branch:** `phase/P26-owner-decisions-adrs`
- **Head commit:** `dc2d8af`
- **Date (UTC):** 2026-10-28
- **Tool versions:** Python 3.12.13 (local .venv), 3.12/3.13 (CI); uv 0.12.2; ruff 0.17.0; mypy 1.20.2; import-linter; deptry; gitleaks; CycloneDX
- **CI run:** https://github.com/aminbita162-glitch/AminOpsTwin/actions/runs/40727934725

## RESULT
IMPLEMENTED (CANDIDATE) — all 7 deliverables implemented, all gates green locally and in CI.

## GATES

| Gate | Command | Result | Evidence |
|------|---------|--------|----------|
| G26.1 | `git grep -n "\[OWNER-FILL" -- docs src ':!docs/archive'` | 0 matches (exit 1) | local; also `git grep -n "tenant-default" -- src` → 0 (exit 1) |
| G26.2 | `pytest tests/governance/test_adr_schema.py -q` | pass (7 ADRs, all Accepted) | reports/P26/evidence/G26.2.txt |
| G26.3 | `pytest tests/contracts/test_idempotency.py::TestConcurrentIdempotency::test_100_concurrent_same_key_one_effect` | pass (1 effect) | reports/P26/evidence/G26.3.txt |
| G26.4 | `pytest tests/contracts/test_idempotency.py::TestConcurrentIdempotency::test_same_key_different_payload_raises_gw_idemp_002` | pass (GW-IDEMP-002) | reports/P26/evidence/G26.4.txt |
| G26.5 | `pytest tests/executor/test_revocation.py::TestRevocation::test_revoke_prevents_commit` | pass (0 commits) | reports/P26/evidence/G26.5.txt |
| G26.6 | `pytest tests/gateway/test_authority_precedence.py` | pass | reports/P26/evidence/G26.6.txt |
| G26.7 | `git grep -n "tenant-default" -- src` → 0 matches (exit 1); `pytest tests/contracts/test_tenant_context.py` | pass | local + reports/P26/evidence/G26.7.txt |
| S1 | `.venv/bin/python -m ruff check src/aminopstwin tests/` | All checks passed | local |
| S2 | `.venv/bin/python -m mypy` | Success: no issues found in 96 source files | local |
| S3 | `.venv/bin/lint-imports` | 2 contracts kept, 0 broken | local |
| S4 | `.venv/bin/python -m pytest --timeout=600 -x -q --tb=short --no-header` with all CI env vars | 3220 passed, 11 skipped, 0 failures (166.53s) | local |
| S5 | charter 17 thresholds | met | CI run 40727934725 |
| S6 | `gitleaks detect` + `pip-audit` | 0 findings | CI run 40727934725 |
| S7 | README and docs describe code | verified | CI run 40727934725 |
| C2-C4 | `python scripts/check_commits.py P26` | ALL PASS | local |
| C7 | `git log --merges origin/main..HEAD` | PASS (0 phase merges) | local |
| CI | all 11 checks on PR #12 | all green | https://github.com/aminbita162-glitch/AminOpsTwin/pull/12 |

## CHANGES
- `docs/adr/ADR-002-licence.md` — added
- `docs/adr/ADR-003-revocation.md` — added
- `docs/adr/ADR-004-idempotency.md` — added
- `docs/adr/ADR-005-audit-anchoring.md` — added
- `docs/adr/ADR-006-unknown-outcomes.md` — added
- `docs/adr/ADR-007-authority-precedence.md` — added
- `docs/adr/ADR-008-sovereign-by-design.md` — added
- `LICENSE` — modified (rewritten per ADR-002)
- `docs/owner_decisions.md` — modified (rewritten as ADR index)
- `docs/open_questions.md` — modified (OQ-P1-001/002/003 closed)
- `docs/claims.yaml` — modified (hashes updated for changed files)
- `docs/gates.yaml` — modified (G26.1–G26.7 registered)
- `docs/reason_code_registry.yaml` — modified (GW-IDEMP-001, GW-IDEMP-002, GW-REVOKE-001, GW-UNK-001–005 added)
- `docs/regulatory_scope/applicability_matrix.yaml` — modified (OWNER-FILL resolved)
- `docs/key_rotation_protocol.md` — modified (OWNER-FILL resolved)
- `docs/source_allowlist.yaml` — modified (OWNER-FILL resolved)
- `docs/schema_scan_exceptions.yaml` — modified (OWNER-FILL resolved)
- `docs/release_notes_v0.2.0-candidate.md` — modified (OWNER-FILL resolved)
- `docs/license_template.txt` — modified (OWNER-FILL resolved, commit d89aef0)
- `src/aminopstwin/priors/public_prior_pack_v1.json` — modified (OWNER-FILL resolved, commit d89aef0)
- `src/aminopstwin/priors/public_prior_pack_v2.json` — modified (OWNER-FILL resolved, commit d89aef0)
- `src/aminopstwin/contracts/idempotency.py` — added (IdempotencyStore port + InMemoryIdempotencyStore)
- `src/aminopstwin/contracts/authority.py` — added (AuthorityLevel enum)
- `src/aminopstwin/contracts/request_context.py` — added (RequestContext with explicit tenant_id)
- `src/aminopstwin/contracts/reasons.py` — modified (new reason codes registered)
- `src/aminopstwin/contracts/__init__.py` — modified (new exports)
- `src/aminopstwin/gateway/gateway.py` — modified (AuthorityDecision + combine_authority)
- `src/aminopstwin/executor/__init__.py` — modified (REVOKED + ESCALATED states, revoke/escalate/re_authorise methods)
- `src/aminopstwin/agents/base.py` — modified (RequestContext support, hard-coded tenant-default removed)
- `src/aminopstwin/contracts/clock.py` — modified (hard-coded tenant-default removed, commit dc2d8af)
- `src/aminopstwin/enterprise/evaluation.py` — modified (hard-coded tenant-default removed, commit dc2d8af)
- `src/aminopstwin/evidence/registry.py` — modified (hard-coded tenant-default removed, commit dc2d8af)
- `src/aminopstwin/integration/integration.py` — modified (hard-coded tenant-default removed, commit dc2d8af)
- `src/aminopstwin/scheduling.py` — modified (hard-coded tenant-default removed, commit dc2d8af)
- `tests/contracts/test_idempotency.py` — added
- `tests/contracts/test_p26_reason_codes.py` — added
- `tests/contracts/test_tenant_context.py` — added (extended in commit dc2d8af)
- `tests/executor/test_revocation.py` — added
- `tests/executor/test_unknown_escalation.py` — added
- `tests/gateway/test_authority_precedence.py` — added
- `tests/governance/test_adr_schema.py` — added
- `tests/governance/test_check_commits.py` — modified (range test for C7)
- `scripts/check_commits.py` — modified (C7 scoped to origin/main..HEAD)
- `reports/P26/PROGRESS.md` — added

## FINDINGS
The previous version of this report (commit ac02438, head `a4f078e`) overstated G26.1 and G26.7:

1. **G26.1 was not fully complete at `a4f078e`.** The initial OWNER-FILL elimination pass missed remaining placeholders in `docs/license_template.txt`, `src/aminopstwin/priors/public_prior_pack_v1.json`, and `src/aminopstwin/priors/public_prior_pack_v2.json`. These were resolved in a follow-up commit (`d89aef0` — "eliminate remaining OWNER-FILL placeholders, recompute prior pack hashes"). The previous report claimed G26.1 was fully done at `a4f078e` with 0 markers remaining, which was inaccurate; the actual clean state was only achieved at `d89aef0`. The current verified state: `git grep -n "\[OWNER-FILL" -- docs src ':!docs/archive'` returns exit 1 (0 matches).

2. **G26.7 was not implemented at `a4f078e`.** The previous report listed G26.7 as a completed deliverable and gate, but the hard-coded `tenant-default` values remained in `src/aminopstwin/agents/base.py`, `clock.py`, `enterprise/evaluation.py`, `evidence/registry.py`, `integration/integration.py`, and `scheduling.py`. These were removed and the tenant made explicit via `RequestContext` in commit `dc2d8af` — "remove all hard-coded tenant-default from src, make tenant explicit". The current verified state: `git grep -n "tenant-default" -- src` returns exit 1 (0 matches).

The previous report's S4 count of "3218 passed" was also inaccurate; the actual local run with all CI env vars and `--timeout=600` yields **3220 passed, 11 skipped, 0 failures**.

## DEVIATION
- `scripts/check_commits.py` C7 merge-commit check was scoped to `origin/main..HEAD` instead of the full branch history. Previously, the P25 merge commit on `main` caused C7 to fail for P26. The fix limits the scan to only commits in the phase range. A test was added in `tests/governance/test_check_commits.py::TestPhaseCommitRange` to verify this behaviour. The CI checkout action may create a merge commit when checking out a PR branch; the test tolerates this by checking that no phase-prefixed merge commits exist.

## PROPOSALS
- The reconciler for UNKNOWN outcomes (ADR-006) is built in P27.
- Cedar policy language (ADR-007 L1) and SMT-based policy analysis (L2) are implemented in P33.
- Signing and timestamping for audit anchoring (ADR-005) are implemented in P32.

## OWNER
No owner actions required. All deliverables are implemented and verified by green CI (run 40727934725, all 11 checks green).
