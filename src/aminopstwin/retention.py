"""Retention / Legal Hold (P20, deliverable 3).

Marks evidence packs as *held*.  A held pack cannot be deleted until
the hold is released by an explicit owner action.

This module is intentionally simple and in-memory: it tracks hold
markers by pack ID and prevents deletion while a hold is active.
The ``HoldReleasedError`` exception is raised if a caller attempts to
delete a held pack.  The module integrates with the evidence pack
infrastructure by operating on pack IDs (strings) — it does not
import the pack itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

__all__ = [
    "HoldError",
    "HoldReleasedError",
    "HoldRecord",
    "RetentionManager",
]


class HoldError(Exception):
    """Base exception for retention / hold errors."""


class HoldReleasedError(HoldError):
    """Raised when a held pack deletion is attempted.

    Despite the name, this exception is raised to *prevent* the
    deletion — it signals that the hold prevented the operation.
    The pack remains on hold and is not deleted.
    """


@dataclass(frozen=True)
class HoldRecord:
    """A single legal-hold record on a pack.

    Attributes:
        pack_id: Identifier of the held pack.
        reason: Human-readable reason for the hold.
        placed_at: UTC timestamp when the hold was placed.
        placed_by: Principal that placed the hold.
    """

    pack_id: str
    reason: str
    placed_at: datetime
    placed_by: str


class RetentionManager:
    """Manage legal holds on evidence packs (P20, deliverable 3).

    A held pack cannot be deleted until its hold is released by an
    explicit owner action (:meth:`release_hold`).  Attempting to delete
    a held pack raises :class:`HoldReleasedError`.

    The manager is in-memory and does not persist across processes —
    it is the interface contract that matters, not the storage backend.
    """

    def __init__(self) -> None:
        self._holds: dict[str, HoldRecord] = {}
        self._deleted: set[str] = set()

    def place_hold(
        self,
        pack_id: str,
        reason: str,
        placed_by: str,
        placed_at: datetime | None = None,
    ) -> HoldRecord:
        """Place a legal hold on *pack_id*.

        Returns the created :class:`HoldRecord`.
        """
        if placed_at is None:
            placed_at = datetime.now(UTC)
        if placed_at.tzinfo is None:
            raise ValueError("placed_at must be timezone-aware (UTC)")
        record = HoldRecord(
            pack_id=pack_id,
            reason=reason,
            placed_at=placed_at,
            placed_by=placed_by,
        )
        self._holds[pack_id] = record
        return record

    def release_hold(self, pack_id: str) -> HoldRecord | None:
        """Release the legal hold on *pack_id*.

        Returns the released :class:`HoldRecord`, or ``None`` if no
        hold was active for that pack.
        """
        return self._holds.pop(pack_id, None)

    def is_held(self, pack_id: str) -> bool:
        """Return True if *pack_id* is currently under a legal hold."""
        return pack_id in self._holds

    def get_hold(self, pack_id: str) -> HoldRecord | None:
        """Return the active :class:`HoldRecord` for *pack_id*, or None."""
        return self._holds.get(pack_id)

    def delete_pack(self, pack_id: str) -> bool:
        """Delete *pack_id* — fails if a hold is active.

        Returns ``True`` if the pack was deleted.  Raises
        :class:`HoldReleasedError` if a hold is active (the pack is NOT
        deleted).
        """
        if self.is_held(pack_id):
            hold = self._holds[pack_id]
            raise HoldReleasedError(
                f"pack {pack_id!r} is under legal hold "
                f"(placed by {hold.placed_by!r}: {hold.reason})"
            )
        if pack_id in self._deleted:
            return False
        self._deleted.add(pack_id)
        return True

    @property
    def held_packs(self) -> dict[str, HoldRecord]:
        """Return a copy of all currently held pack records."""
        return dict(self._holds)

    @property
    def deleted_packs(self) -> frozenset[str]:
        """Return a frozenset of deleted pack IDs."""
        return frozenset(self._deleted)

    @property
    def active_hold_count(self) -> int:
        """Number of active holds."""
        return len(self._holds)
