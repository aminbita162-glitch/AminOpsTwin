# P15 Gate Verification Summary

## G15.1 — Config integrity test passes; no legacy src.* paths
- Test: `tests/p15/test_config_integrity.py` — 12 tests, all pass
- Verifies pyproject.toml, gates.yaml, schema_registry.yaml, invariant_catalog.yaml,
  preservation_mapping.yaml contain no legacy `src.contracts`/`src.gateway` etc. paths
- mypy packages include `aminopstwin.agents` and `aminopstwin.fixtures_gen`
- import-linter: 2 contracts kept (Gateway purity + layer independence)
- Status: PASS

## G15.2 — CI workflow valid YAML with all required jobs
- Jobs: lint, types, test, security, arch, sbom — all present
- Actions pinned by full commit SHA
- Test artifacts uploaded from test_home/
- Status: PASS

## G15.3 — uv lock --check passes
- `uv lock --check` — Resolved 102 packages, 0 drift
- Status: PASS

## G15.4 — README meets professional criteria
- Status table P1–P14 (COMPLETE CANDIDATE) + P15 (ACTIVE) + P16–P20 (NOT STARTED)
- Stage 3 active note
- Architecture diagram with package layout
- Hard-Stop report links for P11–P14
- Measured summary: 2575 passed, 1 skipped, 0 failures
- Claim-id references present
- No placeholder/conversational text
- Email azimilab2025@gmail.com present
- Test: `tests/p15/test_readme.py` — 11 tests, all pass
- Status: PASS

## G15.5 — Authors email is azimilab2025@gmail.com
- `pyproject.toml` authors[0].email = "azimilab2025@gmail.com"
- Status: PASS

## G15.6 — Full regression 0 failures
- Full suite: 2575 passed, 1 skipped, 0 failures (1118.08s)
- Evidence: `test_home/P15/full_regression.txt`
- Status: PASS
