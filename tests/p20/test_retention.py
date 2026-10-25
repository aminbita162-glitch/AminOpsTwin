"""P20 retention / legal hold test (deliverable 3).

Verifies that held evidence packs cannot be deleted until the hold
is released by an explicit owner action.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from aminopstwin.retention import (
    HoldError,
    HoldReleased,
    HoldRecord,
    RetentionManager,
)


class TestRetentionLegalHold:
    """P20 deliverable 3: retention / legal hold."""

    def test_place_hold_marks_pack_as_held(self) -> None:
        """place_hold marks a pack as held."""
        mgr = RetentionManager()
        record = mgr.place_hold(
            "pack-001",
            reason="Audit in progress",
            placed_by="owner",
        )
        assert isinstance(record, HoldRecord)
        assert mgr.is_held("pack-001")
        assert mgr.active_hold_count == 1

    def test_held_pack_cannot_be_deleted(self) -> None:
        """A held pack cannot be deleted."""
        mgr = RetentionManager()
        mgr.place_hold(
            "pack-001",
            reason="Audit",
            placed_by="owner",
        )
        with pytest.raises(HoldReleased):
            mgr.delete_pack("pack-001")

    def test_held_pack_can_be_deleted_after_release(self) -> None:
        """After releasing the hold, the pack can be deleted."""
        mgr = RetentionManager()
        mgr.place_hold(
            "pack-001",
            reason="Audit",
            placed_by="owner",
        )
        released = mgr.release_hold("pack-001")
        assert released is not None
        assert not mgr.is_held("pack-001")
        # Now deletion should succeed
        assert mgr.delete_pack("pack-001") is True

    def test_release_hold_returns_none_if_not_held(self) -> None:
        """release_hold returns None if no hold was active."""
        mgr = RetentionManager()
        assert mgr.release_hold("nonexistent") is None

    def test_get_hold_returns_record(self) -> None:
        """get_hold returns the HoldRecord for a held pack."""
        mgr = RetentionManager()
        mgr.place_hold(
            "pack-001",
            reason="Audit",
            placed_by="owner",
        )
        record = mgr.get_hold("pack-001")
        assert record is not None
        assert record.pack_id == "pack-001"
        assert record.reason == "Audit"
        assert record.placed_by == "owner"

    def test_get_hold_returns_none_if_not_held(self) -> None:
        """get_hold returns None if no hold is active."""
        mgr = RetentionManager()
        assert mgr.get_hold("nonexistent") is None

    def test_delete_pack_not_held_succeeds(self) -> None:
        """A pack that is not held can be deleted."""
        mgr = RetentionManager()
        assert mgr.delete_pack("pack-001") is True
        assert "pack-001" in mgr.deleted_packs

    def test_delete_already_deleted_returns_false(self) -> None:
        """Deleting an already-deleted pack returns False."""
        mgr = RetentionManager()
        assert mgr.delete_pack("pack-001") is True
        assert mgr.delete_pack("pack-001") is False

    def test_multiple_holds(self) -> None:
        """Multiple packs can be held simultaneously."""
        mgr = RetentionManager()
        mgr.place_hold("pack-001", "r1", "owner")
        mgr.place_hold("pack-002", "r2", "owner")
        assert mgr.active_hold_count == 2
        assert mgr.is_held("pack-001")
        assert mgr.is_held("pack-002")

    def test_hold_error_is_base_exception(self) -> None:
        """HoldError is the base exception class."""
        assert issubclass(HoldReleased, HoldError)

    def test_placed_at_must_be_timezone_aware(self) -> None:
        """placed_at must be timezone-aware if provided."""
        mgr = RetentionManager()
        naive = _dt.datetime(2026, 1, 1)
        with pytest.raises(ValueError):
            mgr.place_hold(
                "pack-001",
                reason="Audit",
                placed_by="owner",
                placed_at=naive,
            )

    def test_held_packs_property(self) -> None:
        """held_packs returns a copy of all held records."""
        mgr = RetentionManager()
        mgr.place_hold("pack-001", "r1", "owner")
        held = mgr.held_packs
        assert "pack-001" in held
        # Modifying the returned dict does not affect the manager
        held["pack-999"] = mgr.get_hold("pack-001")  # type: ignore
        assert "pack-999" not in mgr.held_packs
