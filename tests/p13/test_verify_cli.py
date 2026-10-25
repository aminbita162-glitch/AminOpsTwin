"""Tests for the aminopstwin-verify CLI (G13.2).

Verifies that:
- the CLI returns success on valid claims
- the CLI returns failure on tampered hashes
- the CLI can check at least 3 sample claims
- the CLI returns failure on non-existent claim-ids
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
CLAIMS_FILE = REPO_ROOT / "docs" / "claims.yaml"
VERIFY_CLI = REPO_ROOT / "scripts" / "aminopstwin-verify"
PYTHON = sys.executable


def _load_claims() -> list[dict[str, object]]:
    with CLAIMS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return list(data["claims"])


def _run_verify(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(VERIFY_CLI), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=30,
    )


def _compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    if path.is_dir():
        for fp in sorted(path.rglob("*")):
            if fp.is_file():
                h.update(fp.as_posix().encode())
                h.update(b"\0")
                h.update(fp.read_bytes())
    else:
        h.update(path.read_bytes())
    return h.hexdigest()


class TestVerifyCLI:
    """G13.2: verify CLI returns success on valid claim, failure on tampered."""

    def test_verify_all_succeeds(self) -> None:
        """All claims with real hashes should pass verification."""
        result = _run_verify(["--all"])
        assert result.returncode == 0, (
            f"verify --all failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "0 failed" in result.stdout

    def test_verify_three_sample_claims(self) -> None:
        """The directive requires the CLI to check at least 3 sample claims."""
        claims = _load_claims()
        sample_ids = [str(c["claim_id"]) for c in claims[:3]]
        result = _run_verify(sample_ids)
        assert result.returncode == 0, (
            f"verify {sample_ids} failed:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_verify_single_claim_succeeds(self) -> None:
        claims = _load_claims()
        first_id = str(claims[0]["claim_id"])
        result = _run_verify(["--check", first_id])
        assert result.returncode == 0, (
            f"verify --check {first_id} failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_verify_nonexistent_claim_fails(self) -> None:
        result = _run_verify(["NONEXISTENT-999"])
        assert result.returncode != 0, (
            "verify should fail on non-existent claim-id"
        )

    def test_verify_tampered_hash_fails(self, tmp_path: Path) -> None:
        """A claim with a tampered (wrong) hash should fail verification."""
        from collections.abc import Callable
        from typing import Any

        script_globals: dict[str, Any] = {
            "__name__": "aminopstwin_verify",
            "__file__": str(VERIFY_CLI),
        }
        exec(  # noqa: S102
            VERIFY_CLI.read_text(encoding="utf-8"), script_globals
        )
        verify_claim: Callable[..., tuple[bool, str]] = script_globals["verify_claim"]

        claims = _load_claims()
        assert len(claims) >= 1

        # Verify with the real claim (should pass)
        ok, msg = verify_claim(claims[0], REPO_ROOT)
        assert ok, f"valid claim should pass: {msg}"

        # Verify with a tampered hash (should fail)
        tampered = dict(claims[0])
        tampered["hash"] = "0" * 64
        ok2, msg2 = verify_claim(tampered, REPO_ROOT)
        assert not ok2, f"tampered claim should fail: {msg2}"

    def test_verify_missing_evidence_path_fails(self) -> None:
        """A claim pointing to a non-existent file should fail."""
        from collections.abc import Callable
        from typing import Any

        script_globals: dict[str, Any] = {
            "__name__": "aminopstwin_verify",
            "__file__": str(VERIFY_CLI),
        }
        exec(  # noqa: S102
            VERIFY_CLI.read_text(encoding="utf-8"), script_globals
        )
        verify_claim: Callable[..., tuple[bool, str]] = script_globals["verify_claim"]

        fake_claim = {
            "claim_id": "FAKE-999",
            "text": "fake",
            "evidence_path": "nonexistent/file.txt",
            "hash": "0" * 64,
            "category": "test",
        }
        ok, msg = verify_claim(fake_claim, REPO_ROOT)
        assert not ok, "missing evidence path should fail"
        assert "not found" in msg.lower() or "PLACEHOLDER" in msg

    def test_verify_cli_is_executable(self) -> None:
        """The CLI script should have executable permissions."""
        assert os.access(VERIFY_CLI, os.X_OK), (
            "aminopstwin-verify must be executable"
        )
