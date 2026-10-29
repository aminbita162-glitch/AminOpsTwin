"""PostgreSQL adapter for IdempotencyStore (ADR-004, P27).

Implements the IdempotencyStore port with transactional durability.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select

from aminopstwin.contracts.idempotency import (
    IdempotencyError,
    IdempotencyResult,
    IdempotencyStatus,
)
from aminopstwin.persistence.models import IdempotencyKeyModel

__all__ = ["PgIdempotencyStore"]


class PgIdempotencyStore:
    """PostgreSQL adapter for IdempotencyStore (ADR-004).

    Uses row-level locking (SELECT ... FOR UPDATE) to handle concurrent
    access. The composite key (tenant, principal, key) is unique in
    the database, so concurrent inserts with the same key are
    serialised by the unique constraint.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def _result_from_model(
        self, model: IdempotencyKeyModel
    ) -> IdempotencyResult:
        status = IdempotencyStatus(model.status)
        result_data: dict[str, Any] | None = None
        if model.result is not None:
            result_data = json.loads(model.result)
        return IdempotencyResult(
            status=status,
            fingerprint=model.fingerprint,
            effect_id=model.effect_id,
            result=result_data,
        )

    def get_or_start(
        self,
        tenant_id: str,
        principal: str,
        key: str,
        fingerprint: str,
    ) -> tuple[IdempotencyResult, bool]:
        with self._session_factory() as session:
            stmt = (
                select(IdempotencyKeyModel)
                .where(
                    IdempotencyKeyModel.tenant_id == tenant_id,
                    IdempotencyKeyModel.principal == principal,
                    IdempotencyKeyModel.key == key,
                )
                .with_for_update()
            )
            model = session.execute(stmt).scalar_one_or_none()
            if model is not None:
                if model.fingerprint != fingerprint:
                    raise IdempotencyError(
                        f"idempotency key conflict: {key} "
                        f"(expected {model.fingerprint}, "
                        f"got {fingerprint}) [GW-IDEMP-002]"
                    )
                result = self._result_from_model(model)
                session.rollback()
                return result, False
            new_model = IdempotencyKeyModel(
                tenant_id=tenant_id,
                principal=principal,
                key=key,
                status=IdempotencyStatus.IN_PROGRESS.value,
                fingerprint=fingerprint,
            )
            session.add(new_model)
            session.commit()
            return (
                IdempotencyResult(
                    status=IdempotencyStatus.IN_PROGRESS,
                    fingerprint=fingerprint,
                ),
                True,
            )

    def commit(
        self,
        tenant_id: str,
        principal: str,
        key: str,
        effect_id: str,
        result: dict[str, Any],
    ) -> IdempotencyResult:
        with self._session_factory() as session:
            stmt = (
                select(IdempotencyKeyModel)
                .where(
                    IdempotencyKeyModel.tenant_id == tenant_id,
                    IdempotencyKeyModel.principal == principal,
                    IdempotencyKeyModel.key == key,
                )
                .with_for_update()
            )
            model = session.execute(stmt).scalar_one_or_none()
            if model is None:
                raise IdempotencyError(f"cannot commit unknown key: {key}")
            if model.status != IdempotencyStatus.IN_PROGRESS.value:
                raise IdempotencyError(
                    f"cannot commit key in state {model.status}: {key}"
                )
            model.status = IdempotencyStatus.COMMITTED.value
            model.effect_id = effect_id
            model.result = json.dumps(result, sort_keys=True)
            session.commit()
            return IdempotencyResult(
                status=IdempotencyStatus.COMMITTED,
                fingerprint=model.fingerprint,
                effect_id=effect_id,
                result=result,
            )

    def fail(
        self,
        tenant_id: str,
        principal: str,
        key: str,
    ) -> IdempotencyResult:
        with self._session_factory() as session:
            stmt = (
                select(IdempotencyKeyModel)
                .where(
                    IdempotencyKeyModel.tenant_id == tenant_id,
                    IdempotencyKeyModel.principal == principal,
                    IdempotencyKeyModel.key == key,
                )
                .with_for_update()
            )
            model = session.execute(stmt).scalar_one_or_none()
            if model is None:
                raise IdempotencyError(f"cannot fail unknown key: {key}")
            model.status = IdempotencyStatus.FAILED.value
            session.commit()
            return IdempotencyResult(
                status=IdempotencyStatus.FAILED,
                fingerprint=model.fingerprint,
            )

    def get(
        self,
        tenant_id: str,
        principal: str,
        key: str,
    ) -> IdempotencyResult | None:
        with self._session_factory() as session:
            stmt = select(IdempotencyKeyModel).where(
                IdempotencyKeyModel.tenant_id == tenant_id,
                IdempotencyKeyModel.principal == principal,
                IdempotencyKeyModel.key == key,
            )
            model = session.execute(stmt).scalar_one_or_none()
            if model is None:
                return None
            return self._result_from_model(model)
