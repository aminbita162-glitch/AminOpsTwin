"""F10: Policy epoch bumped mid-workflow (G3.10).

Expected: In-flight steps re-validated and re-submitted (§3.7);
COMMIT blocked until re-validation passes.
"""

from __future__ import annotations

from tests.fault.infrastructure import EpochBumpHandler


class TestF10EpochBumpMidWorkflow:
    """F10: Policy epoch bumped mid-workflow."""

    def test_in_flight_marked_for_revalidation(self) -> None:
        """After epoch bump, in-flight steps need revalidation."""
        handler = EpochBumpHandler()
        handler.submit(envelope_epoch=0)
        handler.submit(envelope_epoch=0)
        assert len(handler.in_flight) == 2

        handler.bump_epoch()
        assert handler.current_epoch == 1
        statuses = [e["status"] for e in handler.in_flight]
        assert all(s == "needs_revalidation" for s in statuses)

    def test_commit_blocked_until_revalidation(self) -> None:
        """COMMIT is blocked after epoch bump until revalidation."""
        handler = EpochBumpHandler()
        handler.submit(envelope_epoch=0)
        handler.bump_epoch()

        assert handler.commit_blocked
        assert not handler.commit()

        handler.revalidate()
        assert not handler.commit_blocked
        assert handler.commit()

    def test_revalidation_updates_envelope_epoch(self) -> None:
        """Revalidation updates in-flight envelope epochs."""
        handler = EpochBumpHandler()
        handler.submit(envelope_epoch=0)
        handler.bump_epoch()
        handler.revalidate()

        for entry in handler.in_flight:
            assert entry["envelope_epoch"] == handler.current_epoch
            assert entry["status"] == "revalidated"

    def test_no_commit_without_revalidation(self) -> None:
        """Cannot commit without revalidation after epoch bump."""
        handler = EpochBumpHandler()
        handler.submit(envelope_epoch=0)
        handler.bump_epoch()

        # Attempting to commit without revalidation fails
        assert handler.commit_blocked
        assert not handler.commit()

    def test_multiple_in_flight_all_revalidated(self) -> None:
        """All in-flight steps are revalidated."""
        handler = EpochBumpHandler()
        for _i in range(5):
            handler.submit(envelope_epoch=0)
        handler.bump_epoch()
        handler.revalidate()

        for entry in handler.in_flight:
            assert entry["status"] == "revalidated"
        assert not handler.commit_blocked
