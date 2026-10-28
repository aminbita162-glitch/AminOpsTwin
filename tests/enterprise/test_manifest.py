"""G5.3 — Export manifest hash verification tests (P8).

G5.3: Exports — 100% of files hash-verified against manifests.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from aminopstwin.enterprise.manifest import (
    ManifestError,
    build_manifest,
)


class TestExportManifest:
    """G5.3: 100% of files hash-verified against manifests."""

    def _make_test_files(self, base: Path) -> None:
        """Create test files under *base*."""
        (base / "file1.py").write_text("print('hello')\n")
        (base / "file2.json").write_text('{"key": "value"}\n')
        (base / "subdir").mkdir()
        (base / "subdir" / "file3.py").write_text("# test file\n")
        (base / "README.md").write_text("# Test\n")

    def test_build_manifest_creates_entries(self) -> None:
        """build_manifest creates entries for all matching files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            manifest = build_manifest(base)
            assert manifest.count > 0
            paths = [e.path for e in manifest.entries]
            assert "file1.py" in paths
            assert "file2.json" in paths
            assert "README.md" in paths

    def test_all_entries_hash_verified(self) -> None:
        """100% of entries have valid SHA-256 hashes."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            manifest = build_manifest(base)
            verified = manifest.verify()
            assert verified == manifest.count

    def test_verify_files_match_hashes(self) -> None:
        """Files on disk match their manifest hashes."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            manifest = build_manifest(base)
            verified = manifest.verify_files(base)
            assert verified == manifest.count

    def test_tampered_file_detected(self) -> None:
        """A tampered file raises ManifestError."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            manifest = build_manifest(base)
            # Tamper with a file
            (base / "file1.py").write_text("print('tampered')\n")
            with pytest.raises(ManifestError, match="Hash mismatch"):
                manifest.verify_files(base)

    def test_missing_file_detected(self) -> None:
        """A missing file raises ManifestError."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            manifest = build_manifest(base)
            (base / "file1.py").unlink()
            with pytest.raises(ManifestError, match="File not found"):
                manifest.verify_files(base)

    def test_manifest_serialization(self) -> None:
        """Manifest serializes to JSON and back."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            manifest = build_manifest(base)
            json_str = manifest.to_json()
            data = json.loads(json_str)
            assert data["manifest_version"] == "1.0"
            assert data["count"] == manifest.count

    def test_manifest_entry_fields(self) -> None:
        """Each manifest entry has path, sha256, and size."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            manifest = build_manifest(base)
            for entry in manifest.entries:
                assert entry.path
                assert len(entry.sha256) == 64
                assert entry.size > 0

    def test_manifest_excludes_pycache(self) -> None:
        """Manifest excludes __pycache__ and .venv directories."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            (base / "__pycache__").mkdir()
            (base / "__pycache__" / "test.cpython.pyc").write_bytes(b"")
            manifest = build_manifest(base)
            paths = [e.path for e in manifest.entries]
            assert not any("__pycache__" in p for p in paths)

    def test_manifest_100_percent_verified(self) -> None:
        """G5.3: 100% of files hash-verified against manifests."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            manifest = build_manifest(base)
            verified = manifest.verify()
            assert verified == manifest.count
            assert manifest.count > 0
            # 100% means all entries verified
            assert verified / manifest.count == 1.0
