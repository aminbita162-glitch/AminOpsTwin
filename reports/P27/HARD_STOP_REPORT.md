# P27 — Real Persistence: Hard-Stop Report

**Branch:** phase/P27-real-persistence
**Head commit:** bd36c72
**Date (UTC):** 2026-10-29T14:50:00+00:00

## Tool Versions
- Python: 3.12.13 (uv)
- ruff: 0.17.0
- mypy: 2.4.0
- import-linter: 2.15
- Docker: 29.5.3

## RESULT
IMPLEMENTED (CANDIDATE) — review findings fixed; remaining deliverables in progress.

## GATES

| Gate | Command | Result | Evidence |
|------|---------|--------|----------|
| G27.1 | `pytest tests/executor/test_fault_injection.py -q` | PENDING | reports/P27/evidence/G27.1.txt |
| G27.2 | `pytest tests/executor/test_postgres_idempotency.py -q` | PENDING | reports/P27/evidence/G27.2.txt |
| G27.3 | `pytest tests/enterprise/test_rls_postgres.py -q` | PENDING | reports/P27/evidence/G27.3.txt |
| G27.4 | `pytest tests/evidence/test_audit_storage.py -q` | PENDING | reports/P27/evidence/G27.4.txt |
| G27.5 | `pytest tests/formal/test_executor_tla.py -q` | PENDING | reports/P27/evidence/G27.5.txt |
| G27.6 | `pytest tests/executor/test_seeded_fault_harness.py -q` | PENDING | reports/P27/evidence/G27.6.txt |
| G27.7 | `pytest tests/executor/test_migrations.py -q` | PENDING | reports/P27/evidence/G27.7.txt |
| G27.8 | `pytest tests/enterprise/test_rls_removed.py -q` | PENDING | reports/P27/evidence/G27.8.txt |

## CHANGES
- reports/P27/HARD_STOP_REPORT.md: created (records the overstatement finding)

## FINDINGS

### F1 (HIGH): Commit 0e6583a overstates G27.1, G27.2, G27.3, G27.4, G27.8 as complete
Commit `0e6583a` ("P27: PostgreSQL 16 persistence layer, adapters, compose,
RLS removal (G27.1, G27.2, G27.3, G27.4, G27.8, INFRA)") claims G27.1, G27.2,
G27.3, G27.4, and G27.8, but none of the test files named by the gate
source_commands in `docs/gates.yaml` existed at that commit:

- `tests/executor/test_fault_injection.py` — G27.1 — MISSING
- `tests/executor/test_postgres_idempotency.py` — G27.2 — MISSING
- `tests/enterprise/test_rls_postgres.py` — G27.3 — MISSING
- `tests/evidence/test_audit_storage.py` — G27.4 — MISSING
- `tests/enterprise/test_rls_removed.py` — G27.8 — MISSING

Only G27.5's test file (`tests/formal/test_executor_tla.py`) existed at that
commit (added in commit `bd36c72`). No gate counts as passed until its
`source_command` in `docs/gates.yaml` runs green. These gates are being
implemented as part of this resumed session; the test files will be created
and run green before any gate is marked as passing.

### F2 (HIGH): alembic.ini is outside ALLOWED PATHS
The P27 card's ALLOWED PATHS list includes `migrations/` but not the
repository root. `alembic.ini` at the repo root is therefore outside the
allowed paths. It must be moved to `migrations/alembic.ini` and every
reference updated. (Fixed in this session.)

### F3 (MEDIUM): Postgres gate tests may be skipped on Linux
The Postgres-dependent gate tests (G27.1–G27.4, G27.8) must never be skipped
on Linux. In CI they must run via testcontainers on the ubuntu job and that
job must fail if they are skipped. They may skip only on the macOS job,
which has no container runtime.

### F4 (MEDIUM): G27.5 runs nowhere today
The TLC model check (G27.5) must run in the ubuntu CI job, with
`tla2tools.jar` pinned by SHA-256 and every action pinned by commit SHA. In
CI the test must fail, never skip, if TLC is missing.

### F5 (HIGH): TLS private keys must not be committed
Test certificates must be generated at runtime, outside the repository. No
default credentials may appear anywhere in the repository.

## PROPOSALS
None at this time.

## OWNER
None at this time.
