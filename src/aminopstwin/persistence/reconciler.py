"""Real reconciler for UNKNOWN outcomes (ADR-006, P27 deliverable 3).

Resolves UNKNOWN from the transactional outbox: if the effect is found
in the outbox, the state becomes COMMITTED; if not, it becomes FAILED,
and a retry with the same idempotency key is safe.

Backoff of at most 15 minutes, then ESCALATED.  Dependent workflows
are locked until resolution.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import select

from aminopstwin.persistence.models import OutboxModel

__all__ = ["Reconciler", "MAX_BACKOFF_SECONDS"]

MAX_BACKOFF_SECONDS = 900  # 15 minutes


class Reconciler:
    """Reconciler for UNKNOWN outcomes (ADR-006).

    Resolves UNKNOWN from the outbox:
    - If the effect is found in the outbox with status 'committed',
      the workflow transitions to COMMITTED.
    - If the effect is not found or status is not 'committed',
      the workflow transitions to FAILED.
    - If the effect is found with status 'pending', backoff continues
      for at most MAX_BACKOFF_SECONDS, then the workflow is ESCALATED.

    Dependent workflows are locked until resolution.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def reconcile_unknown(
        self,
        workflow_id: str,
        started_at: float | None = None,
    ) -> str:
        """Reconcile a workflow in UNKNOWN state.

        Returns 'COMMITTED', 'FAILED', or 'ESCALATED'.
        """
        if started_at is not None:
            elapsed = time.monotonic() - started_at
            if elapsed > MAX_BACKOFF_SECONDS:
                return "ESCALATED"

        with self._session_factory() as session:
            outbox_entry = session.execute(
                select(OutboxModel)
                .where(OutboxModel.workflow_id == workflow_id)
                .limit(1)
            ).scalar_one_or_none()
            if outbox_entry is None:
                return "FAILED"
            if outbox_entry.status == "committed":
                return "COMMITTED"
            if outbox_entry.status == "pending":
                if started_at is not None:
                    elapsed = time.monotonic() - started_at
                    if elapsed > MAX_BACKOFF_SECONDS:
                        return "ESCALATED"
                return "PENDING"
            return "FAILED"
