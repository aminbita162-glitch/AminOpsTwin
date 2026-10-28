# P26 — Owner Decisions as ADRs and Core Semantics — PROGRESS

## Phase
P26 — Owner Decisions as ADRs and Core Semantics

## Branch
`phase/P26-owner-decisions-adrs`

## Status
IMPLEMENTED (CANDIDATE)

## Completed deliverables
1. **ADRs** — ADR-002 to ADR-008 written in `docs/adr/` in MADR format
   with status Accepted, deciders "Owner", context, decision,
   consequences, and proof tests. LICENSE rewritten per ADR-002.
2. **OWNER-FILL elimination** — All `[OWNER-FILL]` markers resolved
   in `applicability_matrix.yaml`, `key_rotation_protocol.md`,
   `source_allowlist.yaml`, `schema_scan_exceptions.yaml`,
   `release_notes_v0.2.0-candidate.md`, `license_template.txt`,
   `open_questions.md`, `public_prior_pack_v1.json`,
   `public_prior_pack_v2.json`. `owner_decisions.md` rewritten
   as ADR index. `open_questions.md` updated (OQ-P1-001/002/003 closed).
   Prior pack OWNER-FILL values replaced with "NOT_SIGNED: out of
   scope until P32; see ADR-005". CLAIM-013 hash recomputed.
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
   `TENANT_DEFAULT` constant removed from `clock.py`. All default
   tenant parameters removed from `src/`. All callers in `src/` and
   `tests/` pass tenant explicitly. Test added that greps `src/` for
   "tenant-default" and fails if found.

## Gates
- G26.1: `git grep -n "[OWNER-FILL" -- docs src` (excl. `docs/archive/`) -> 0 matches
- G26.2: ADR schema test -> pass (7 ADRs, all Accepted)
- G26.3: 100 concurrent same-key -> 1 effect -> pass
- G26.4: same key different payload -> GW-IDEMP-002 -> pass
- G26.5: revocation prevents commit -> pass
- G26.6: authority precedence deny-overrides -> pass
- G26.7: `git grep -n "tenant-default" -- src` -> 0 matches; test_no_tenant_default_in_src -> pass
- S1: ruff check src/aminopstwin tests/ -> clean
- S2: mypy -> 0 errors (96 files)
- S3: lint-imports -> all contracts kept
- S4: pytest -> 3220 passed, 11 skipped, 0 failures

## Full suite result
3220 passed, 11 skipped, 0 failures (with CI env vars
AMINOPS_REGRESSION_NESTED=1 and all P14–P24 nested vars).

## CI
All 11 checks on PR #12 green.
CI run: https://github.com/aminbita162-glitch/AminOpsTwin/actions/runs/40727934725
PR: https://github.com/aminbita162-glitch/AminOpsTwin/pull/12
Head commit: dc2d8af

## Findings
The previous Hard-Stop Report (commit ac02438) overstated G26.1 and
G26.7 as PASS when they were not yet met. G26.1 had remaining
OWNER-FILL markers in license_template.txt, the prior pack JSON
files, and open_questions.md. G26.7 had "tenant-default" in 8 src/
files as the TENANT_DEFAULT constant and as default parameter
values. Both were corrected: G26.1 in commit d89aef0, G26.7 in
commit dc2d8af.
