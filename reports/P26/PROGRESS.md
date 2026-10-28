# P26 — Owner Decisions as ADRs and Core Semantics — PROGRESS

## Phase
P26 — Owner Decisions as ADRs and Core Semantics

## Branch
`phase/P26-owner-decisions-adrs`

## Status
IMPLEMENTED (CANDIDATE)

## Current head commit
`dc2d8af`

## Completed deliverables
1. **ADRs** — ADR-002 to ADR-008 written in `docs/adr/` in MADR format
   with status Accepted, deciders "Owner", context, decision,
   consequences, and proof tests. LICENSE rewritten per ADR-002.
2. **OWNER-FILL elimination** — All `[OWNER-FILL]` markers resolved
   in `applicability_matrix.yaml`, `key_rotation_protocol.md`,
   `source_allowlist.yaml`, `schema_scan_exceptions.yaml`,
   `release_notes_v0.2.0-candidate.md`, `docs/license_template.txt`,
   `src/aminopstwin/priors/public_prior_pack_v1.json`,
   `src/aminopstwin/priors/public_prior_pack_v2.json`.
   `owner_decisions.md` rewritten as ADR index. `open_questions.md`
   updated (OQ-P1-001/002/003 closed). Initial pass (ac02438) missed
   remaining markers in license_template.txt and prior packs; fixed
   in d89aef0.
3. **Idempotency (ADR-004)** — `IdempotencyStore` protocol + thread-safe
   `InMemoryIdempotencyStore` in `contracts/idempotency.py`.
   `GW-IDEMP-001`, `GW-IDEMP-002` registered.
4. **Revocation (ADR-003)** — `REVOKED` state in executor,
   `revoke()`/`re_authorise()` methods. `GW-REVOKE-001` registered.
5. **UNKNOWN semantics (ADR-006)** — `ESCALATED` state in executor,
   `escalate()` method. `GW-UNK-001` to `GW-UNK-005` registered.
6. **Authority precedence (ADR-007)** — `AuthorityLevel` enum (6
   levels), `combine_authority()` deny-overrides in gateway.
7. **Tenant and causation** — `RequestContext` carrying explicit
   `tenant_id`/`causation_id`. `BaseAgent.process()` updated.
   All hard-coded `tenant-default` values removed from `src/` (commit
   dc2d8af): `agents/base.py`, `contracts/clock.py`,
   `enterprise/evaluation.py`, `evidence/registry.py`,
   `integration/integration.py`, `scheduling.py`.

## Gates
- G26.1: `git grep -n "\[OWNER-FILL" -- docs src ':!docs/archive'` → exit 1 (0 matches)
- G26.2: ADR schema test -> pass (7 ADRs, all Accepted)
- G26.3: 100 concurrent same-key -> 1 effect -> pass
- G26.4: same key different payload -> GW-IDEMP-002 -> pass
- G26.5: revocation prevents commit -> pass
- G26.6: authority precedence deny-overrides -> pass
- G26.7: `git grep -n "tenant-default" -- src` → exit 1 (0 matches); `pytest tests/contracts/test_tenant_context.py` -> pass
- S1: `.venv/bin/python -m ruff check src/aminopstwin tests/` -> clean
- S2: `.venv/bin/python -m mypy` -> 0 errors (96 files)
- S3: `.venv/bin/lint-imports` -> 2 contracts kept, 0 broken
- S4: `.venv/bin/python -m pytest --timeout=600 -x -q --tb=short --no-header` with all CI env vars -> 3220 passed, 11 skipped, 0 failures (166.53s)

## Full suite result
3220 passed, 11 skipped, 0 failures (with CI env vars
PYTHONHASHSEED=0, AMINOPS_REGRESSION_NESTED=1 and all P14–P24 nested vars,
pytest --timeout=600 -x).

## CI
All 11 checks on PR #12 green.
CI run: https://github.com/aminbita162-glitch/AminOpsTwin/actions/runs/40727934725

## Corrected report
The previous Hard-Stop Report (commit ac02438, head a4f078e) overstated
G26.1 and G26.7. G26.1 required a follow-up commit (d89aef0) to eliminate
remaining OWNER-FILL placeholders in license_template.txt and prior packs.
G26.7 was not implemented at a4f078e; the hard-coded tenant-default removal
was done in dc2d8af. The corrected report is at reports/P26/HARD_STOP_REPORT.md.
