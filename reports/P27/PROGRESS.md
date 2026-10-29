# P27 — Real Persistence: Progress Log

**Branch:** phase/P27-real-persistence
**Status:** IN_PROGRESS

## Deliverables

| # | Deliverable | Status | Notes |
|---|------------|--------|-------|
| 1 | PostgreSQL 16 via SQLAlchemy 2 + psycopg 3; compose.yaml | DONE | compose.yaml, alembic.ini, models, session, base |
| 2 | PostgreSQL adapters for every P26 port | DONE | pg_executor, pg_idempotency, pg_audit, reconciler, rls_setup |
| 3 | Real reconciler (ADR-006) | DONE | reconciler.py with 15-min backoff + ESCALATED |
| 4 | Real RLS: ENABLE + FORCE; delete in-memory sim | DONE | rls_setup.py; enterprise/rls.py gutted to re-export |
| 5 | Audit storage (ADR-005): append-only, hash chain, Merkle | DONE | pg_audit.py with hash chain + Merkle batching |
| 6 | formal/executor.tla: TLA+ spec, TLC checks | NOT_STARTED | |
| 7 | Seeded fault-injection harness | NOT_STARTED | |
| 8 | Connection security: TLS, env-only credentials | DONE | session.py PGConfig.from_env, sslmode=verify-full |
| 9 | Alembic migrations; docs/schema.md | NOT_STARTED | |

## Gate Registration
- G27.1–G27.8 registered in docs/gates.yaml (first commit).

## Baseline
- Pre-flight full suite: 3220 passed, 11 skipped, 0 failures.
- Docker: running (Docker 29.5.3).
- Python: 3.12.13 (uv). ruff 0.17.0, mypy 2.4.0, import-linter 2.15.

## Session Log
- Session 1: created branch, registered gates, running baseline.
- Session 2: committed deliverables 1-5, 8 (persistence layer + RLS removal). ruff/mypy/import-linter/deptry clean. Next: deliverable 6 (TLA+), 7 (fault harness), 9 (migrations + schema docs).
- Head: 0e6583a
