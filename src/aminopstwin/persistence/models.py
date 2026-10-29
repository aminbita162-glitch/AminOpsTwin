"""SQLAlchemy ORM models for the persistence layer (P27).

Tables:
    workflows, checkpoints, effects, idempotency_keys (unique on
    tenant, principal, key), outbox, audit_events, merkle_batches

The transactional outbox writes the effect receipt in the same
transaction as the effect (ADR-004 / ADR-006).
"""

from __future__ import annotations

import datetime as _dt

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aminopstwin.persistence.base import Base

__all__ = [
    "WorkflowModel",
    "CheckpointModel",
    "EffectModel",
    "IdempotencyKeyModel",
    "OutboxModel",
    "AuditEventModel",
    "MerkleBatchModel",
]


# ---------------------------------------------------------------------------
# Workflows
# ---------------------------------------------------------------------------


class WorkflowModel(Base):
    """A persisted workflow record (maps to DurableExecutor state)."""

    __tablename__ = "workflows"

    workflow_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    history: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    checkpoints: Mapped[list[CheckpointModel]] = relationship(
        "CheckpointModel",
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    effects: Mapped[list[EffectModel]] = relationship(
        "EffectModel",
        back_populates="workflow",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# Checkpoints
# ---------------------------------------------------------------------------


class CheckpointModel(Base):
    """A persisted checkpoint for a workflow."""

    __tablename__ = "checkpoints"
    __table_args__ = (
        Index("ix_checkpoints_workflow_seq", "workflow_id", "sequence_no"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workflows.workflow_id"),
        nullable=False,
    )
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    workflow: Mapped[WorkflowModel] = relationship(
        "WorkflowModel", back_populates="checkpoints"
    )


# ---------------------------------------------------------------------------
# Effects (committed effects)
# ---------------------------------------------------------------------------


class EffectModel(Base):
    """A committed effect (outcome of a workflow commit)."""

    __tablename__ = "effects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    effect_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    workflow_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workflows.workflow_id"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    committed_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    workflow: Mapped[WorkflowModel] = relationship(
        "WorkflowModel", back_populates="effects"
    )


# ---------------------------------------------------------------------------
# Idempotency keys (unique on tenant, principal, key)
# ---------------------------------------------------------------------------


class IdempotencyKeyModel(Base):
    """An idempotency key entry (ADR-004).

    Unique on (tenant, principal, key).
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "principal",
            "key",
            name="uq_idempotency_tenant_principal_key",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    principal: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    effect_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


# ---------------------------------------------------------------------------
# Transactional outbox
# ---------------------------------------------------------------------------


class OutboxModel(Base):
    """Transactional outbox: effect receipt in the same transaction (ADR-006)."""

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    effect_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    processed_at: Mapped[_dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


# ---------------------------------------------------------------------------
# Audit events (append-only)
# ---------------------------------------------------------------------------


class AuditEventModel(Base):
    """An append-only audit event (ADR-005).

    Audit storage is write-once: no role may UPDATE or DELETE.
    The application role has no UPDATE or DELETE privileges on this
    table (enforced by the migration and by a role without
    BYPASSRLS).
    """

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    record_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[int] = mapped_column(Integer, nullable=False)
    event: Mapped[str] = mapped_column(String(128), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


# ---------------------------------------------------------------------------
# Merkle batches
# ---------------------------------------------------------------------------


class MerkleBatchModel(Base):
    """A Merkle batch root (ADR-005).

    Batches are built every 15 minutes or every 1000 events, whichever
    comes first. Roots are persisted unsigned; signing and
    timestamping are added in P32.
    """

    __tablename__ = "merkle_batches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    root_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    first_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    last_event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[_dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
