"""G17.4 — Offline Verification Kit: verify_pack.py on a known-good pack (P17).

Tests that the standalone verify_pack.py script validates a known-good
pack produced by the system, and rejects a tampered pack.  The script
does not import the main application — it uses only stdlib.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
VERIFY_PACK = REPO_ROOT / "scripts" / "verify_pack.py"
AMINOPS_VERIFY = REPO_ROOT / "scripts" / "aminopstwin-verify"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_pack(tmp_path: Path) -> Path:
    """Create a known-good evidence pack and return its directory."""
    pack = tmp_path / "good_pack"
    pack.mkdir()
    (pack / "file_a.txt").write_text("AAA")
    (pack / "file_b.txt").write_text("BBB")
    (pack / "file_c.txt").write_text("CCC")

    # Build manifest.
    files = sorted(
        (f for f in pack.rglob("*") if f.is_file()),
        key=lambda p: p.as_posix(),
    )
    manifest_entries = []
    hashes = []
    for f in files:
        rel = f.relative_to(pack).as_posix()
        h = _sha256(f.read_bytes())
        manifest_entries.append({"file_name": rel, "sha256": h})
        hashes.append(h)

    # Compute merkle root.
    def _hash_pair(left: str, right: str) -> str:
        return hashlib.sha256((left + right).encode("utf-8")).hexdigest()

    level = list(hashes)
    while len(level) > 1:
        next_level = []
        i = 0
        while i < len(level):
            left = level[i]
            if i + 1 < len(level):
                right = level[i + 1]
                next_level.append(_hash_pair(left, right))
                i += 2
            else:
                next_level.append(_hash_pair(left, left))
                i += 1
        level = next_level
    merkle_root = level[0] if level else _sha256(b"")

    manifest = {
        "files": manifest_entries,
        "merkle_root": merkle_root,
    }
    (pack / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return pack


class TestOfflineKit:
    """G17.4: offline verification kit succeeds on a known-good pack."""

    def test_verify_pack_good_pack(self, tmp_path: Path) -> None:
        """verify_pack.py succeeds on a known-good pack."""
        pack = _make_pack(tmp_path)
        result = subprocess.run(
            [sys.executable, str(VERIFY_PACK), str(pack)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"verify_pack failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "PACK VERIFIED" in result.stdout

    def test_verify_pack_tampered_file(self, tmp_path: Path) -> None:
        """verify_pack.py fails on a tampered file."""
        pack = _make_pack(tmp_path)
        # Tamper with a file.
        (pack / "file_a.txt").write_text("TAMPERED")
        result = subprocess.run(
            [sys.executable, str(VERIFY_PACK), str(pack)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1, (
            f"verify_pack should have failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "FAIL" in result.stdout

    def test_verify_pack_missing_manifest(self, tmp_path: Path) -> None:
        """verify_pack.py fails when the manifest is missing."""
        pack = tmp_path / "no_manifest"
        pack.mkdir()
        (pack / "a.txt").write_text("A")
        result = subprocess.run(
            [sys.executable, str(VERIFY_PACK), str(pack)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1

    def test_verify_pack_missing_file(self, tmp_path: Path) -> None:
        """verify_pack.py fails when a manifest file is missing."""
        pack = tmp_path / "missing_file"
        pack.mkdir()
        manifest = {
            "files": [{"file_name": "ghost.txt", "sha256": "a" * 64}],
        }
        (pack / "manifest.json").write_text(json.dumps(manifest))
        result = subprocess.run(
            [sys.executable, str(VERIFY_PACK), str(pack)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1
        assert "FAIL" in result.stdout

    def test_verify_pack_no_merkle_root(self, tmp_path: Path) -> None:
        """verify_pack.py succeeds without a merkle_root (just file hashes)."""
        pack = tmp_path / "no_root"
        pack.mkdir()
        (pack / "a.txt").write_text("A")
        h = _sha256(b"A")
        manifest = {"files": [{"file_name": "a.txt", "sha256": h}]}
        (pack / "manifest.json").write_text(json.dumps(manifest))
        result = subprocess.run(
            [sys.executable, str(VERIFY_PACK), str(pack)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

    def test_verify_pack_explicit_manifest(self, tmp_path: Path) -> None:
        """verify_pack.py --manifest works with an explicit manifest path."""
        pack = _make_pack(tmp_path)
        manifest_path = tmp_path / "custom_manifest.json"
        manifest_path.write_text((pack / "manifest.json").read_text())
        result = subprocess.run(
            [
                sys.executable,
                str(VERIFY_PACK),
                str(pack),
                "--manifest",
                str(manifest_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0

    def test_verify_pack_missing_dir(self, tmp_path: Path) -> None:
        """verify_pack.py fails on a non-existent pack directory."""
        result = subprocess.run(
            [sys.executable, str(VERIFY_PACK), str(tmp_path / "nonexistent")],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1

    def test_verify_cli_graph_flag(self) -> None:
        """aminopstwin-verify --graph works on the real repo."""
        result = subprocess.run(
            [sys.executable, str(AMINOPS_VERIFY), "--graph"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"--graph failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_verify_cli_partial_proof_flag(self, tmp_path: Path) -> None:
        """aminopstwin-verify --partial-proof verifies a Merkle proof."""
        pack = _make_pack(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(AMINOPS_VERIFY),
                "--partial-proof",
                str(pack),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"--partial-proof failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_verify_cli_partial_proof_named_file(self, tmp_path: Path) -> None:
        """aminopstwin-verify --partial-proof --file <name> verifies a specific file."""
        pack = _make_pack(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(AMINOPS_VERIFY),
                "--partial-proof",
                str(pack),
                "--file",
                "file_b.txt",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"--partial-proof --file failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_verify_cli_partial_proof_nonexistent_file(self, tmp_path: Path) -> None:
        """aminopstwin-verify --partial-proof fails on a non-existent file."""
        pack = _make_pack(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(AMINOPS_VERIFY),
                "--partial-proof",
                str(pack),
                "--file",
                "nonexistent.txt",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 1

    def test_verify_pack_does_not_import_app(self) -> None:
        """verify_pack.py does not import aminopstwin."""
        # Read the script and check it doesn't import the main app.
        content = VERIFY_PACK.read_text()
        assert "import aminopstwin" not in content
        assert "from aminopstwin" not in content
