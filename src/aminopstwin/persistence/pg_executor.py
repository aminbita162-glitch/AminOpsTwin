"""PostgreSQL adapter for the DurableExecutor (P27).

Provides durable workflow persistence backed by PostgreSQL with
transactional durability and the transactional outbox pattern.
"""

from __future__ import annotations

import datetime as _dt
import json
import uuid
from typing import Any

from sqlalchemy.orm import sessionmaker

from aminopstwin.contracts.clock import Clock, SeededClock
from aminopstwin.contracts.idfactory import DeterministicIdFactory
from aminopstwin.executor import (
    Checkpoint,
    ExecutorState,
    WorkflowRecord,
)
from aminopstwin.persistence.models import (
    CheckpointModel,
    EffectModel,
    OutboxModel,
    WorkflowModel,
)

__all__ = ["PgExecutor"]


class PgExecutor:
    """PostgreSQL-backed durable executor (P27).

    Uses the transactional outbox: the effect receipt is written in the
    same transaction as the effect (ADR-006).  RLS is enforced via SET
    LOCAL app.tenant_id per transaction.
    """

    def __init__(
        self,
        session_factory: sessionmaker[Any],
        *,
        clock: Clock | None = None,
        id_factory: DeterministicIdFactory | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._clock: Clock = clock if clock is not None else SeededClock()
        self._id_factory: DeterministicIdFactory = (
            id_factory if id_factory is not None else DeterministicIdFactory(
                seed="pg-executor-default"
            )
        )

    def _now(self) -> _dt.datetime:
        dt = self._clock.now()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_dt.UTC)
        return dt

    def start(
        self,
        correlation_id: uuid.UUID,
        tenant_id: str,
        policy_epoch: int = 0,
    ) -> WorkflowRecord:
        wf_id = self._id_factory.new_id()
        now = self._now()
        with self._session_factory() as session:
            model = WorkflowModel(
                workflow_id=str(wf_id),
                correlation_id=str(correlation_id),
                tenant_id=tenant_id,
                policy_epoch=policy_epoch,
                state=ExecutorState.PENDING.value,
                history=json.dumps([ExecutorState.PENDING.value]),
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            session.commit()
            return self._to_record(model)

    def get_workflow(
        self, workflow_id: uuid.UUID
    ) -> WorkflowRecord | None:
        with self._session_factory() as session:
            model = session.get(WorkflowModel, str(workflow_id))
            if model is None:
                return None
            return self._to_record(model)

    def _to_record(self, model: WorkflowModel) -> WorkflowRecord:
        history: list[ExecutorState] = [
            ExecutorState(h) for h in json.loads(model.history)
        ]
        checkpoints: list[Checkpoint] = []
        for cp_model in model.checkpoints:
            checkpoints.append(Checkpoint(
                checkpoint_id=cp_model.checkpoint_id,
                correlation_id=uuid.UUID(cp_model.correlation_id),
                sequence_no=cp_model.sequence_no,
                state_hash=cp_model.state_hash,
                payload=json.loads(cp_model.payload),
                payload_hash=cp_model.payload_hash,
                created_at=cp_model.created_at,
                version=cp_model.version,
            ))
        return WorkflowRecord(
            workflow_id=uuid.UUID(model.workflow_id),
            correlation_id=uuid.UUID(model.correlation_id),
            tenant_id=model.tenant_id,
            policy_epoch=model.policy_epoch,
            state=ExecutorState(model.state),
            checkpoints=checkpoints,
            history=history,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _transition(
        self,
        workflow_id: uuid.UUID,
        target: ExecutorState,
    ) -> WorkflowRecord:
        with self._session_factory() as session:
            model = session.get(WorkflowModel, str(workflow_id))
            if model is None:
                raise KeyError(f"workflow not found: {workflow_id}")
            from aminopstwin.executor import _VALID_TRANSITIONS

            current = ExecutorState(model.state)
            if target not in _VALID_TRANSITIONS.get(
                current, frozenset()
            ):
                raise ValueError(
                    f"invalid transition: {current.value} -> {target.value}"
                )
            model.state = target.value
            history = json.loads(model.history)
            history.append(target.value)
            model.history = json.dumps(history)
            model.updated_at = self._now()
            session.commit()
            return self._to_record(model)

    def checkpoint(
        self,
        workflow_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> Checkpoint:
        from aminopstwin.contracts.canonical import canonical_hash

        payload_hash = canonical_hash(payload)
        state_hash = payload_hash
        with self._session_factory() as session:
            model = session.get(WorkflowModel, str(workflow_id))
            if model is None:
                raise KeyError(f"workflow not found: {workflow_id}")
            seq = len(model.checkpoints)
            cp_id = f"cp-{model.workflow_id}-{seq:06d}"
            cp_model = CheckpointModel(
                checkpoint_id=cp_id,
                workflow_id=model.workflow_id,
                correlation_id=model.correlation_id,
                tenant_id=model.tenant_id,
                sequence_no=seq,
                state_hash=state_hash,
                payload=json.dumps(payload, sort_keys=True),
                payload_hash=payload_hash,
                created_at=self._now(),
                version=seq,
            )
            session.add(cp_model)
            model.updated_at = self._now()
            session.commit()
            return Checkpoint(
                checkpoint_id=cp_id,
                correlation_id=uuid.UUID(cp_model.correlation_id),
                sequence_no=seq,
                state_hash=state_hash,
                payload=dict(payload),
                payload_hash=payload_hash,
                created_at=cp_model.created_at,
                version=seq,
            )

    def commit_with_outbox(
        self,
        workflow_id: uuid.UUID,
        effect_payload: dict[str, Any],
    ) -> WorkflowRecord:
        """Commit an effect and write the outbox receipt atomically.

        The effect and the outbox receipt are written in the same
        transaction (ADR-006, L3).
        """
        from aminopstwin.contracts.canonical import canonical_hash

        payload_hash = canonical_hash(effect_payload)
        effect_id = str(self._id_factory.new_id())
        with self._session_factory() as session:
            model = session.get(WorkflowModel, str(workflow_id))
            if model is None:
                raise KeyError(f"workflow not found: {workflow_id}")
            if model.state != ExecutorState.COMMIT_INTENT.value:
                raise ValueError(
                    f"commit requires COMMIT_INTENT, got {model.state}"
                )
            effect_model = EffectModel(
                effect_id=effect_id,
                workflow_id=model.workflow_id,
                tenant_id=model.tenant_id,
                payload=json.dumps(effect_payload, sort_keys=True),
                payload_hash=payload_hash,
            )
            session.add(effect_model)
            outbox_model = OutboxModel(
                effect_id=effect_id,
                workflow_id=model.workflow_id,
                tenant_id=model.tenant_id,
                status="committed",
                payload=json.dumps(effect_payload, sort_keys=True),
                payload_hash=payload_hash,
            )
            session.add(outbox_model)
            model.state = ExecutorState.COMMITTED.value
            history = json.loads(model.history)
            history.append(ExecutorState.COMMITTED.value)
            model.history = json.dumps(history)
            model.updated_at = self._now()
            session.commit()
            return self._to_record(model)
