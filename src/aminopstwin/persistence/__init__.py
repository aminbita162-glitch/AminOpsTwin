"""PostgreSQL persistence layer for AminOpsTwin (P27).

Provides SQLAlchemy 2 (2.0-style) and psycopg 3 based adapters for the
P26 domain ports.  Tables:

    workflows, checkpoints, effects, idempotency_keys (unique on
    tenant, principal, key), outbox, audit_events, merkle_batches

The transactional outbox writes the effect receipt in the same
transaction as the effect (ADR-004 / ADR-006).
"""

from __future__ import annotations

from aminopstwin.persistence.base import Base, get_engine, get_session_factory
from aminopstwin.persistence.models import (
    AuditEventModel,
    CheckpointModel,
    EffectModel,
    IdempotencyKeyModel,
    MerkleBatchModel,
    OutboxModel,
    WorkflowModel,
)
from aminopstwin.persistence.reconciler import Reconciler
from aminopstwin.persistence.session import (
    PGConfig,
    create_pg_engine,
    create_pg_session_factory,
    set_tenant_local,
)

__all__ = [
    "Base",
    "get_engine",
    "get_session_factory",
    "AuditEventModel",
    "CheckpointModel",
    "EffectModel",
    "IdempotencyKeyModel",
    "MerkleBatchModel",
    "OutboxModel",
    "WorkflowModel",
    "Reconciler",
    "PGConfig",
    "create_pg_engine",
    "create_pg_session_factory",
    "set_tenant_local",
]
