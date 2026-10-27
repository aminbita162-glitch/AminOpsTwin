# P25 Progress Report

## Phase: P25 — Truth Reset
## Branch: phase/P25-truth-reset
## Status: IN PROGRESS

## Completed Deliverables

1. **Directive governance re-baseline** — DONE (committed)
   - Retired tests/p22/test_directive_consistency.py and
     tests/p22/test_owner_fill_eliminated.py to docs/archive/retired_tests/.
   - Retired scripts/check_directive_consistency.py to
     docs/archive/check_directive_consistency.py.txt.
   - Created tests/governance/test_directive_format.py (5 tests).
   - Generalised scripts/check_commits.py: P1–P99, gate IDs from gates.yaml.
   - Added tests/governance/test_check_commits.py (43 tests).
   - Updated tests/p22/test_gate_source_consistency.py for dynamic loading.

2. **Three-level status model** — DONE (committed)
   - Wrote docs/status_model.md (GOVERNANCE / IMPLEMENTED / VERIFIED).

3. **Dependency truth** — DONE (committed)
   - Removed unused runtime deps: sqlalchemy, alembic, psycopg, networkx, simpy.
   - Added pyyaml as explicit runtime dependency (used in claim_graph.py).
   - Added deptry to dev deps and CI; configured in pyproject.toml.

8. **Single source for type checking** — DONE (committed)
   - CI mypy job now uses `uv run mypy` (no package list).
   - Package list lives only in pyproject.toml [tool.mypy] packages.

9. **Python 3.12 and 3.13** — DONE (committed)
   - requires-python = ">=3.12,<3.14".
   - CI test matrix covers 3.12 and 3.13 on x86_64 and arm64.

4. **Remove false claims (docstrings)** — DONE (committed)
   - twin/simulation.py: removed SimPy claim.
   - enterprise/rls.py: states "in-memory simulation until P27".
   - executor/__init__.py: states "in-memory, no durability until P27".
   - dashboard/app.py: states "auth not implemented until P33".

## Open Deliverables

4. (remainder) Rename "signature" → "integrity tag (HMAC)" in
   assurance/signed_pack.py, stage_seal.py, stage4_seal.py,
   integration/exports.py. Rewrite README Architecture, Technology,
   Measured Summary, phase status table.
5. Separate documentation tests from engineering tests.
6. Domain-based test layout (git mv tests/p4–p24).
7. Skip registry.
10. Code hygiene: replace __import__("hashlib") in agents/base.py.
11. Permanent claim guard: docs/claims_map.yaml + test_claim_guard.py.
12. Intended-purpose record: docs/regulatory/intended_purpose.md.

## Baseline Failures (9 test ids)

The following 9 test ids failed at pre-flight (clause 4.4). All are
known baseline exceptions per the P25 card: tests that assert the
content of the retired Stage 4 directive.

1. tests/p21/test_regression.py::TestFullRegression::test_full_regression_passes
2. tests/p22/test_directive_consistency.py::TestDirectiveConsistency::test_single_active_phase_sequence
3. tests/p22/test_directive_consistency.py::TestDirectiveConsistency::test_p1_through_p20_complete
4. tests/p22/test_directive_consistency.py::TestDirectiveConsistency::test_status_vocabulary
5. tests/p22/test_directive_consistency.py::TestDirectiveConsistency::test_consistency_script_passes
6. tests/p22/test_owner_fill_eliminated.py::TestOwnerFillEliminated::test_directive_has_all_four_stage4_phases
7. tests/p22/test_regression.py::TestFullRegression::test_full_regression_passes
8. tests/p23/test_regression.py::TestFullRegression::test_full_regression_passes
9. tests/p24/test_regression.py::TestFullRegression::test_full_regression_passes

Tests 2–6 assert the retired Stage 4 directive content.
Tests 1, 7, 8, 9 are nested regression tests that run the full suite
and hit tests 2–6.

Baseline summary: 3088 passed, 7 skipped, 9 failed, 5 warnings.

## Current Branch Head

```
6d3bf91 P25: remove false claims about SimPy, RLS, executor durability, and dashboard auth (INFRA)
```

## Next Step

Deliverable 4 remainder: rename "signature" → "integrity tag (HMAC)"
in assurance/signed_pack.py, stage_seal.py, stage4_seal.py,
integration/exports.py; rewrite README.
