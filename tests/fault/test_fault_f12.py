"""F12: Disk full / write failure (G3.10).

Expected: Stop new writes; explicit FAILED when no effect committed;
UNKNOWN if the outcome cannot be established. Use a bounded independent
error channel when the primary store cannot write.
"""

from __future__ import annotations

from tests.fault.infrastructure import DiskFullWriter


class TestF12DiskFullWriteFailure:
    """F12: Disk full / write failure."""

    def test_stop_new_writes_on_disk_full(self) -> None:
        """When disk is full, new writes are stopped."""
        writer = DiskFullWriter()
        assert writer.new_write_status == "ACCEPTING"

        writer.set_disk_full()
        assert writer.disk_full
        assert writer.new_write_status == "STOPPED"

    def test_explicit_failed_when_no_effect_committed(self) -> None:
        """When disk is full, writes report FAILED."""
        writer = DiskFullWriter()
        writer.set_disk_full()

        result = writer.write(b"data content here")
        assert result["status"] == "FAILED"
        assert result["effect_committed"] is False
        assert result["bytes_written"] == 0
        assert result["error"] == "disk_full"

    def test_unknown_when_outcome_not_establishable(self) -> None:
        """When the outcome cannot be established, report UNKNOWN."""
        writer = DiskFullWriter()
        writer.set_disk_full()

        result = writer.write_with_uncertain_outcome(b"data")
        assert result["status"] == "UNKNOWN"
        assert result["effect_committed"] is False
        assert result["error"] == "disk_full_during_write"

    def test_bounded_independent_error_channel(self) -> None:
        """Failures are recorded in a bounded independent error channel."""
        writer = DiskFullWriter()
        writer.set_disk_full()

        writer.write(b"data1")
        writer.write(b"data2")
        writer.write_with_uncertain_outcome(b"data3")

        entries = writer.error_channel_entries
        assert len(entries) == 3
        assert any("write_failed:disk_full" in e for e in entries)
        assert any("write_uncertain" in e for e in entries)

    def test_no_silent_loss(self) -> None:
        """Failed writes do not silently succeed."""
        writer = DiskFullWriter()
        writer.set_disk_full()

        result = writer.write(b"important data")
        assert result["status"] != "SUCCESS"
        assert result["effect_committed"] is False

    def test_reconciliation_after_recovery(self) -> None:
        """After recovery, the error channel can be reconciled."""
        writer = DiskFullWriter()
        writer.set_disk_full()
        writer.write(b"data1")
        writer.write(b"data2")

        # Disk is freed
        writer.clear_disk_full()
        result = writer.reconcile(primary_store_available=True)
        assert result == "RECONCILED"
        assert any("reconciled" in e for e in writer.error_channel_entries)

    def test_reconciliation_still_unavailable(self) -> None:
        """If the primary store is still unavailable, report so."""
        writer = DiskFullWriter()
        writer.set_disk_full()
        result = writer.reconcile(primary_store_available=False)
        assert result == "STILL_UNAVAILABLE"

    def test_successful_write_after_recovery(self) -> None:
        """After recovery, writes succeed normally."""
        writer = DiskFullWriter()
        writer.set_disk_full()
        writer.write(b"failed data")

        writer.clear_disk_full()
        result = writer.write(b"success data")
        assert result["status"] == "SUCCESS"
        assert result["effect_committed"] is True
        assert result["bytes_written"] == len(b"success data")

    def test_no_timeout_success(self) -> None:
        """A disk-full write is never mistaken for a timeout success."""
        writer = DiskFullWriter()
        writer.set_disk_full()
        result = writer.write(b"data")
        # The status must be FAILED, not SUCCESS
        assert result["status"] == "FAILED"
