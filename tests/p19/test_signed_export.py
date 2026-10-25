"""G19.2 — Signed export verifies offline; tampered export fails (P19).

Tests:
  - build_export_bundle produces an unsigned bundle;
  - sign_bundle produces a SIGNED bundle with a valid signature;
  - co_sign_bundle attaches an optional co-signature;
  - verify_bundle validates a signed bundle;
  - the offline verify_export.py script validates a known-good export;
  - a tampered export fails verification.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from aminopstwin.integration.exports import (
    NO_AGENT_HELD_KEY,
    ExportSignatureError,
    ExportSignatureStatus,
    build_export_bundle,
    co_sign_bundle,
    sign_bundle,
    verify_bundle,
)

REPO_ROOT = Path(__file__).parent.parent.parent
HEX64_A = "a" * 64
HEX64_B = "b" * 64


@pytest.fixture()
def export_dir(tmp_path: Path) -> Path:
    """Create a temporary export directory with files."""
    d = tmp_path / "export"
    d.mkdir()
    (d / "data1.json").write_text('{"key": "value1"}\n', encoding="utf-8")
    (d / "data2.json").write_text('{"key": "value2"}\n', encoding="utf-8")
    (d / "readme.md").write_text("# Export\n", encoding="utf-8")
    return d


class TestBuildExportBundle:
    """build_export_bundle produces an unsigned bundle."""

    def test_build_unsigned_bundle(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        assert bundle.signature_status == ExportSignatureStatus.UNSIGNED
        assert bundle.signature_hash is None
        assert bundle.co_signature_hash is None
        assert bundle.bundle_hash is not None
        assert len(bundle.bundle_hash) == 64

    def test_agent_holds_no_key(self) -> None:
        assert NO_AGENT_HELD_KEY is True


class TestSignBundle:
    """sign_bundle produces a SIGNED bundle with a valid signature."""

    def test_sign_bundle(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        signed = sign_bundle(bundle, HEX64_A)
        assert signed.signature_status == ExportSignatureStatus.SIGNED
        assert signed.signature_hash == HEX64_A

    def test_sign_rejects_invalid_hash(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        with pytest.raises(ExportSignatureError):
            sign_bundle(bundle, "short")

    def test_sign_rejects_non_hex(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        with pytest.raises(ExportSignatureError):
            sign_bundle(bundle, "z" * 64)


class TestCoSignature:
    """co_sign_bundle attaches an optional co-signature."""

    def test_co_sign_bundle(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        signed = sign_bundle(bundle, HEX64_A)
        co_signed = co_sign_bundle(signed, HEX64_B)
        assert co_signed.signature_hash == HEX64_A
        assert co_signed.co_signature_hash == HEX64_B

    def test_co_sign_preserves_primary(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        co_signed = co_sign_bundle(bundle, HEX64_B)
        assert co_signed.co_signature_hash == HEX64_B
        assert co_signed.signature_status == ExportSignatureStatus.UNSIGNED

    def test_co_sign_rejects_invalid(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        with pytest.raises(ExportSignatureError):
            co_sign_bundle(bundle, "short")


class TestVerifyBundle:
    """verify_bundle validates signed bundles and co-signatures."""

    def test_verify_signed_bundle(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        signed = sign_bundle(bundle, HEX64_A)
        count = verify_bundle(signed, export_dir)
        assert count > 0

    def test_verify_co_signed_bundle(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        signed = sign_bundle(bundle, HEX64_A)
        co_signed = co_sign_bundle(signed, HEX64_B)
        count = verify_bundle(co_signed, export_dir)
        assert count > 0

    def test_verify_unsigned_bundle(self, export_dir: Path) -> None:
        bundle = build_export_bundle(export_dir)
        count = verify_bundle(bundle, export_dir)
        assert count > 0

    def test_verify_invalid_co_signature_raises(self, export_dir: Path) -> None:
        from dataclasses import replace

        bundle = build_export_bundle(export_dir)
        bad_bundle = replace(bundle, co_signature_hash="short")
        with pytest.raises(ExportSignatureError):
            verify_bundle(bad_bundle, export_dir)


class TestOfflineVerifyScript:
    """The standalone verify_export.py script validates exports offline."""

    def _write_bundle_json(
        self, export_dir: Path, *, signed: bool = True, co_signed: bool = False
    ) -> None:
        """Write a bundle.json alongside the export."""
        bundle_data: dict[str, str | None] = {
            "signature_status": "signed" if signed else "unsigned",
            "signature_hash": HEX64_A if signed else None,
            "co_signature_hash": HEX64_B if co_signed else None,
        }
        (export_dir / "bundle.json").write_text(
            json.dumps(bundle_data, indent=2) + "\n", encoding="utf-8"
        )

    def test_offline_verify_good_export(self, export_dir: Path) -> None:
        from aminopstwin.enterprise.manifest import build_manifest

        manifest = build_manifest(export_dir)
        manifest_path = export_dir / "manifest.json"
        manifest_path.write_text(manifest.to_json() + "\n", encoding="utf-8")
        self._write_bundle_json(export_dir, signed=True, co_signed=True)

        script = REPO_ROOT / "scripts" / "verify_export.py"
        result = subprocess.run(
            [sys.executable, str(script), str(export_dir)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"offline verify failed:\n{result.stdout}\n{result.stderr}"
        )

    def test_offline_verify_tampered_file_fails(self, export_dir: Path) -> None:
        from aminopstwin.enterprise.manifest import build_manifest

        manifest = build_manifest(export_dir)
        manifest_path = export_dir / "manifest.json"
        manifest_path.write_text(manifest.to_json() + "\n", encoding="utf-8")
        self._write_bundle_json(export_dir, signed=True)

        # Tamper with a file after the manifest is written.
        (export_dir / "data1.json").write_text(
            '{"key": "TAMPERED"}\n', encoding="utf-8"
        )

        script = REPO_ROOT / "scripts" / "verify_export.py"
        result = subprocess.run(
            [sys.executable, str(script), str(export_dir)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 1, (
            f"tampered export should fail:\n{result.stdout}\n{result.stderr}"
        )
        assert "FAIL" in result.stdout

    def test_offline_verify_missing_manifest_fails(
        self, tmp_path: Path
    ) -> None:
        d = tmp_path / "empty_export"
        d.mkdir()
        script = REPO_ROOT / "scripts" / "verify_export.py"
        result = subprocess.run(
            [sys.executable, str(script), str(d)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 1

    def test_offline_verify_invalid_co_signature_fails(
        self, export_dir: Path
    ) -> None:
        from aminopstwin.enterprise.manifest import build_manifest

        manifest = build_manifest(export_dir)
        manifest_path = export_dir / "manifest.json"
        manifest_path.write_text(manifest.to_json() + "\n", encoding="utf-8")

        bundle_data: dict[str, object] = {
            "signature_status": "signed",
            "signature_hash": HEX64_A,
            "co_signature_hash": "short",
        }
        (export_dir / "bundle.json").write_text(
            json.dumps(bundle_data, indent=2) + "\n", encoding="utf-8"
        )

        script = REPO_ROOT / "scripts" / "verify_export.py"
        result = subprocess.run(
            [sys.executable, str(script), str(export_dir)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 1
        assert "co_signature" in result.stdout
