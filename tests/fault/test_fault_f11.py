"""F11: Export interrupted mid-write (G3.10).

Expected: No partial file is visible under the final name; the
manifest is absent; a retry is clean.

F11 is tested on a minimal atomic export-write primitive in P3;
the complete product export workflow remains in P5 (§37).
"""

from __future__ import annotations

import os
import tempfile

from tests.fault.infrastructure import AtomicExportWriter


class TestF11ExportInterrupted:
    """F11: Export interrupted mid-write."""

    def test_no_partial_file_visible_after_interruption(
        self, tmp_path: str
    ) -> None:
        """After an interrupted write, the final file does not exist."""
        writer = AtomicExportWriter(str(tmp_path))
        content = b"export data content here" * 100

        temp_path = writer.write_export_interrupted(
            "export.json", content
        )

        # The final file must not exist
        assert not writer.final_file_exists("export.json")
        # The temp file exists (but is not the final name)
        assert os.path.exists(temp_path)

    def test_manifest_absent_after_interruption(
        self, tmp_path: str
    ) -> None:
        """After an interrupted write, the manifest is absent."""
        writer = AtomicExportWriter(str(tmp_path))
        content = b"export data" * 100

        writer.write_export_interrupted("export.json", content)
        assert not writer.manifest_exists("export.json")

    def test_retry_is_clean(self, tmp_path: str) -> None:
        """After interruption, a retry produces the correct file."""
        writer = AtomicExportWriter(str(tmp_path))
        content = b"export data content" * 100

        # First attempt interrupted
        writer.write_export_interrupted("export.json", content)
        assert not writer.final_file_exists("export.json")

        # Retry succeeds
        final_path = writer.retry_write(
            "export.json",
            content,
            manifest={"hash": "abc123"},
        )
        assert writer.final_file_exists("export.json")
        assert os.path.exists(final_path)

        # Content matches
        with open(final_path, "rb") as f:
            assert f.read() == content

    def test_manifest_written_after_successful_export(
        self, tmp_path: str
    ) -> None:
        """A successful export writes both the file and the manifest."""
        writer = AtomicExportWriter(str(tmp_path))
        content = b"export data" * 50

        final_path = writer.write_export(
            "export.json",
            content,
            manifest={"hash": "def456"},
        )
        assert writer.final_file_exists("export.json")
        assert writer.manifest_exists("export.json")
        assert os.path.exists(final_path)

    def test_atomic_write_no_partial_visible(self, tmp_path: str) -> None:
        """An atomic write leaves no partial file visible."""
        writer = AtomicExportWriter(str(tmp_path))
        content = b"atomic export data" * 200

        final_path = writer.write_export("atomic.json", content)
        assert writer.final_file_exists("atomic.json")

        # Content must be complete
        with open(final_path, "rb") as f:
            assert f.read() == content
