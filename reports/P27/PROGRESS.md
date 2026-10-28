# P27 — Real Persistence: Progress Log

**Branch:** phase/P27-real-persistence
**Status:** IN_PROGRESS

## Deliverables

| # | Deliverable | Status | Notes |
|---|------------|--------|-------|
| 1 | PostgreSQL 16 via SQLAlchemy 2 + psycopg 3; compose.yaml | NOT_STARTED | |
| 2 | PostgreSQL adapters for every P26 port | NOT_STARTED | |
| 3 | Real reconciler (ADR-006) | NOT_STARTED | |
| 4 | Real RLS: ENABLE + FORCE; delete in-memory sim | NOT_STARTED | |
| 5 | Audit storage (ADR-005): append-only, hash chain, Merkle | NOT_STARTED | |
| 6 | formal/executor.tla: TLA+ spec, TLC checks | NOT_STARTED | |
| 7 | Seeded fault-injection harness | NOT_STARTED | |
| 8 | Connection security: TLS, env-only credentials | NOT_STARTED | |
| 9 | Alembic migrations; docs/schema.md | NOT_STARTED | |

## Gate Registration
- G27.1–G27.8 registered in docs/gates.yaml (first commit).

## Baseline
- Pre-flight full suite: 3220 passed, 11 skipped, 0 failures.
- Docker: running (Docker 29.5.3).
- Python: 3.12.13 (uv). ruff 0.17.0, mypy 2.4.0, import-linter 2.15.

## Session Log
- Session 1: created branch, registered gates, running baseline.
