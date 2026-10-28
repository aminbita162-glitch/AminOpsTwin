"""Idempotency store port and in-memory adapter (ADR-004).

Every effectful operation requires an Idempotency-Key supplied by the
caller. The key scope is (tenant, principal, key). The fingerprint is
the canonical hash of the payload.

- Same key, same fingerprint: the stored result is returned; nothing
  is executed again.
- Same key, different fingerprint: denied with GW-IDEMP-002 (HTTP 409).
- Duplicate while the first request is still in progress: an
  in-progress response is returned, with no second execution.

Keys live 7 days at the API layer. Committed effect ids are permanent.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

__all__ = [
    "IdempotencyStatus",
    "IdempotencyResult",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "IdempotencyError",
]


class IdempotencyStatus(StrEnum):
    """Status of an idempotency key entry."""

    IN_PROGRESS = "IN_PROGRESS"
    COMMITTED = "COMMITTED"
    FAILED = "FAILED"


class IdempotencyError(Exception):
    """Raised when an idempotency check fails (e.g. key conflict)."""


@dataclass(frozen=True, slots=True)
class IdempotencyResult:
    """The stored result of an effectful operation keyed by idempotency key.

    Attributes:
        status: the current status (IN_PROGRESS, COMMITTED, FAILED).
        fingerprint: the canonical hash of the payload that was first
            submitted with this key.
        effect_id: the permanent effect id, set when COMMITTED.
        result: the stored result payload, set when COMMITTED.
    """

    status: IdempotencyStatus
    fingerprint: str
    effect_id: str | None = None
    result: dict[str, Any] | None = None


class IdempotencyStore(Protocol):
    """Port for idempotency key storage (ADR-004).

    The store is keyed by (tenant_id, principal, key). It is thread-safe.
    """

    def get_or_start(
        self,
        tenant_id: str,
        principal: str,
        key: str,
        fingerprint: str,
    ) -> tuple[IdempotencyResult, bool]:
        """Get an existing entry or start a new one.

        Returns (result, started_new). If an entry exists:
        - same fingerprint: return the stored result, started_new=False.
        - different fingerprint: raise IdempotencyError with code
          GW-IDEMP-002.
        If no entry exists, create an IN_PROGRESS entry and return
        (result, True).
        """
        ...

    def commit(
        self,
        tenant_id: str,
        principal: str,
        key: str,
        effect_id: str,
        result: dict[str, Any],
    ) -> IdempotencyResult:
        """Transition an IN_PROGRESS entry to COMMITTED with the effect id."""
        ...

    def fail(
        self,
        tenant_id: str,
        principal: str,
        key: str,
    ) -> IdempotencyResult:
        """Transition an IN_PROGRESS entry to FAILED."""
        ...

    def get(
        self,
        tenant_id: str,
        principal: str,
        key: str,
    ) -> IdempotencyResult | None:
        """Read an entry without side effects, or None if not found."""
        ...


def _make_key(tenant_id: str, principal: str, key: str) -> str:
    """Build the composite key for the store."""
    return f"{tenant_id}:{principal}:{key}"


class InMemoryIdempotencyStore:
    """Thread-safe in-memory adapter for IdempotencyStore (ADR-004).

    This adapter is used in P26. P27 provides a PostgreSQL adapter that
    implements the same port with transactional durability.
    """

    def __init__(self) -> None:
        self._lock: threading.Lock = threading.Lock()
        self._store: dict[str, IdempotencyResult] = {}

    def get_or_start(
        self,
        tenant_id: str,
        principal: str,
        key: str,
        fingerprint: str,
    ) -> tuple[IdempotencyResult, bool]:
        with self._lock:
            composite = _make_key(tenant_id, principal, key)
            existing = self._store.get(composite)
            if existing is not None:
                if existing.fingerprint != fingerprint:
                    raise IdempotencyError(
                        f"idempotency key conflict: {key} "
                        f"(expected {existing.fingerprint}, "
                        f"got {fingerprint}) [GW-IDEMP-002]"
                    )
                return existing, False
            result = IdempotencyResult(
                status=IdempotencyStatus.IN_PROGRESS,
                fingerprint=fingerprint,
            )
            self._store[composite] = result
            return result, True

    def commit(
        self,
        tenant_id: str,
        principal: str,
        key: str,
        effect_id: str,
        result: dict[str, Any],
    ) -> IdempotencyResult:
        with self._lock:
            composite = _make_key(tenant_id, principal, key)
            existing = self._store.get(composite)
            if existing is None:
                raise IdempotencyError(
                    f"cannot commit unknown key: {key}"
                )
            if existing.status is not IdempotencyStatus.IN_PROGRESS:
                raise IdempotencyError(
                    f"cannot commit key in state {existing.status}: {key}"
                )
            committed = IdempotencyResult(
                status=IdempotencyStatus.COMMITTED,
                fingerprint=existing.fingerprint,
                effect_id=effect_id,
                result=result,
            )
            self._store[composite] = committed
            return committed

    def fail(
        self,
        tenant_id: str,
        principal: str,
        key: str,
    ) -> IdempotencyResult:
        with self._lock:
            composite = _make_key(tenant_id, principal, key)
            existing = self._store.get(composite)
            if existing is None:
                raise IdempotencyError(
                    f"cannot fail unknown key: {key}"
                )
            failed = IdempotencyResult(
                status=IdempotencyStatus.FAILED,
                fingerprint=existing.fingerprint,
            )
            self._store[composite] = failed
            return failed

    def get(
        self,
        tenant_id: str,
        principal: str,
        key: str,
    ) -> IdempotencyResult | None:
        with self._lock:
            composite = _make_key(tenant_id, principal, key)
            return self._store.get(composite)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
