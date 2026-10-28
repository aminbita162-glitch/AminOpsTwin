# P26 — Hard-Stop Report

## HEADER
- **Phase:** P26 — Owner Decisions as ADRs and Core Semantics
- **Branch:** `phase/P26-owner-decisions-adrs`
- **Head commit:** `a4f078e`
- **Date (UTC):** 2026-10-28 14:56
- **Tool versions:** Python 3.11.15 (local), 3.12/3.13 (CI); uv 0.12.2; ruff 0.17.0; mypy 1.20.2; import-linter; deptry; gitleaks; CycloneDX

## RESULT
IMPLEMENTED (CANDIDATE) — all 7 deliverables implemented, all gates green locally and in CI.

## GATES

| Gate | Command | Result | Evidence |
|------|---------|--------|----------|
| G26.1 | `grep -rn OWNER-FILL .` (excl. detection patterns) | 0 actual markers | reports/P26/evidence/G26.1.txt |
| G26.2 | `pytest tests/governance/test_adr_schema.py -q` | pass (7 ADRs, all Accepted) | reports/P26/evidence/G26.2.txt |
| G26.3 | `pytest tests/contracts/test_idempotency.py::TestConcurrentIdempotency::test_100_concurrent_same_key_one_effect` | pass (1 effect) | reports/P26/evidence/G26.3.txt |
| G26.4 | `pytest tests/contracts/test_idempotency.py::TestConcurrentIdempotency::test_same_key_different_payload_raises_gw_idemp_002` | pass (GW-IDEMP-002) | reports/P26/evidence/G26.4.txt |
| G26.5 | `pytest tests/executor/test_revocation.py::TestRevocation::test_revoke_prevents_commit` | pass (0 commits) | reports/P26/evidence/G26.5.txt |
| G26.6 | `pytest tests/gateway/test_authority_precedence.py` | pass | reports/P26/evidence/G26.6.txt |
| G26.7 | `pytest tests/contracts/test_tenant_context.py` | pass | reports/P26/evidence/G26.7.txt |
| S1 | `uv run ruff check src/aminopstwin tests/` | clean | CI run 40709190115 |
| S2 | `uv run mypy` | 0 errors (96 files) | CI run 40709190115 |
| S3 | `uv run lint-imports` | 2 contracts kept, 0 broken | CI run 40709190115 |
| S4 | `uv run pytest` | 3218 passed, 11 skipped, 0 failures | CI run 40709190115 |
| S5 | charter 17 thresholds | met | CI run 40709190115 |
| S6 | `gitleaks detect` + `pip-audit` | 0 findings | CI run 40709190115 |
| S7 | README and docs describe code | verified | CI run 40709190115 |
| C2-C4 | `python3 scripts/check_commits.py P26` | ALL PASS | local |
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
- `src/aminopstwin/contracts/idempotency.py` — added (IdempotencyStore port + InMemoryIdempotencyStore)
- `src/aminopstwin/contracts/authority.py` — added (AuthorityLevel enum)
- `src/aminopstwin/contracts/request_context.py` — added (RequestContext)
- `src/aminopstwin/contracts/reasons.py` — modified (new reason codes registered)
- `src/aminopstwin/contracts/__init__.py` — modified (new exports)
- `src/aminopstwin/gateway/gateway.py` — modified (AuthorityDecision + combine_authority)
- `src/aminopstwin/executor/__init__.py` — modified (REVOKED + ESCALATED states, revoke/escalate/re_authorise methods)
- `src/aminopstwin/agents/base.py` — modified (RequestContext support)
- `tests/contracts/test_idempotency.py` — added
- `tests/contracts/test_p26_reason_codes.py` — added
- `tests/contracts/test_tenant_context.py` — added
- `tests/executor/test_revocation.py` — added
- `tests/executor/test_unknown_escalation.py` — added
- `tests/gateway/test_authority_precedence.py` — added
- `tests/governance/test_adr_schema.py` — added
- `tests/governance/test_check_commits.py` — modified (range test for C7)
- `scripts/check_commits.py` — modified (C7 scoped to origin/main..HEAD)
- `reports/P26/PROGRESS.md` — added

## FINDINGS
None. All gates green locally and in CI.

## DEVIATION
- `scripts/check_commits.py` C7 merge-commit check was scoped to `origin/main..HEAD` instead of the full branch history. Previously, the P25 merge commit on `main` caused C7 to fail for P26. The fix limits the scan to only commits in the phase range. A test was added in `tests/governance/test_check_commits.py::TestPhaseCommitRange` to verify this behaviour. The CI checkout action may create a merge commit when checking out a PR branch; the test tolerates this by checking that no phase-prefixed merge commits exist.

## PROPOSALS
- The reconciler for UNKNOWN outcomes (ADR-006) is built in P27.
- Cedar policy language (ADR-007 L1) and SMT-based policy analysis (L2) are implemented in P33.
- Signing and timestamping for audit anchoring (ADR-005) are implemented in P32.

## OWNER
No owner actions required. All deliverables are implemented and verified by green CI.
