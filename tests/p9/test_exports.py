"""G6.1/G6.3 — Signed exports tests (P9).

Tests the signed export bundle workflow from §38 operational rule 7:
  - Bundles are UNSIGNED by default.
  - Signing is simulated by the owner providing a hash (no agent-held key).
  - A SIGNED bundle has a 64-char hex signature_hash.
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pytest
from src.integration.exports import (
    NO_AGENT_HELD_KEY,
    ExportSignatureError,
    ExportSignatureStatus,
    build_export_bundle,
    sign_bundle,
    verify_bundle,
)


class TestExportBundle:
    """Signed export bundle tests (§38 rule 7, G5.3/G6.1)."""

    def _make_test_files(self, base: Path) -> None:
        """Create test files under *base*."""
        (base / "file1.py").write_text("print('hello')\n")
        (base / "file2.json").write_text('{"key": "value"}\n')
        (base / "README.md").write_text("# Test\n")

    def test_build_export_bundle_creates_unsigned(self) -> None:
        """build_export_bundle creates an UNSIGNED bundle."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            assert bundle.signature_status == ExportSignatureStatus.UNSIGNED
            assert bundle.signature_hash is None
            assert bundle.bundle_hash != ""

    def test_export_bundle_is_frozen(self) -> None:
        """ExportBundle is frozen."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            with pytest.raises((AttributeError, TypeError)):
                bundle.bundle_id = "other"  # type: ignore[misc]

    def test_bundle_hash_is_sha256(self) -> None:
        """bundle_hash is a 64-char hex string."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            assert len(bundle.bundle_hash) == 64
            assert all(c in "0123456789abcdef" for c in bundle.bundle_hash)

    def test_bundle_hash_is_deterministic(self) -> None:
        """Same files produce the same bundle hash."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle1 = build_export_bundle(base)
            bundle2 = build_export_bundle(base)
            assert bundle1.bundle_hash == bundle2.bundle_hash

    def test_verify_bundle_returns_count(self) -> None:
        """verify_bundle returns the number of verified files."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            verified = verify_bundle(bundle, base)
            assert verified == bundle.manifest.count

    def test_sign_bundle_sets_signed_status(self) -> None:
        """sign_bundle returns a SIGNED bundle with a signature_hash."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            owner_hash = hashlib.sha256(b"owner-signature").hexdigest()
            signed = sign_bundle(bundle, owner_hash)
            assert signed.signature_status == ExportSignatureStatus.SIGNED
            assert signed.signature_hash == owner_hash
            assert len(signed.signature_hash) == 64

    def test_sign_bundle_rejects_invalid_hash(self) -> None:
        """sign_bundle rejects a non-64-char hex signature."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            with pytest.raises(ExportSignatureError):
                sign_bundle(bundle, "short")

    def test_sign_bundle_rejects_non_hex(self) -> None:
        """sign_bundle rejects a non-hex signature."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            bad_hash = "z" * 64
            with pytest.raises(ExportSignatureError):
                sign_bundle(bundle, bad_hash)

    def test_unsigned_bundle_has_no_signature(self) -> None:
        """An UNSIGNED bundle has signature_hash=None."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            assert bundle.signature_hash is None
            assert bundle.signature_status == ExportSignatureStatus.UNSIGNED

    def test_no_agent_held_key(self) -> None:
        """NO_AGENT_HELD_KEY is True — no agent holds a signing key."""
        assert NO_AGENT_HELD_KEY is True

    def test_sign_bundle_does_not_mutate_original(self) -> None:
        """sign_bundle returns a new bundle; the original stays UNSIGNED."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            owner_hash = hashlib.sha256(b"owner").hexdigest()
            signed = sign_bundle(bundle, owner_hash)
            assert bundle.signature_status == ExportSignatureStatus.UNSIGNED
            assert signed.signature_status == ExportSignatureStatus.SIGNED

    def test_export_bundle_has_created_at(self) -> None:
        """ExportBundle has a created_at timestamp."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            assert bundle.created_at
            assert len(bundle.created_at) > 0

    def test_export_bundle_has_bundle_id(self) -> None:
        """ExportBundle has a bundle_id."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            self._make_test_files(base)
            bundle = build_export_bundle(base)
            assert bundle.bundle_id
            assert len(bundle.bundle_id) > 0
