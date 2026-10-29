"""Test the TLA+ executor specification (P27, G27.5).

The TLA+ spec at formal/executor.tla formalises the executor state
machine including UNKNOWN, REVOKED, ESCALATED, and reconciliation.

TLC checks:
    NoDoubleEffect     — at most one committed effect per workflow
    NoLostEffect       — a COMPLETED workflow always has a committed effect
    EventualResolution — every UNKNOWN eventually resolves

If TLC (tla2tools.jar) is available on the CLASSPATH, we run the model
checker. Otherwise, we verify the spec file exists and contains the
required properties and state definitions.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

FORMAL_DIR = Path(__file__).resolve().parent.parent.parent / "formal"
TLA_SPEC = FORMAL_DIR / "executor.tla"
TLA_CFG = FORMAL_DIR / "executor.cfg"


class TestTLASpecExists:
    """G27.5 — the TLA+ specification file exists."""

    def test_spec_file_exists(self) -> None:
        assert TLA_SPEC.exists(), f"TLA+ spec not found at {TLA_SPEC}"

    def test_cfg_file_exists(self) -> None:
        assert TLA_CFG.exists(), f"TLA+ config not found at {TLA_CFG}"


class TestTLASpecStructure:
    """G27.5 — the spec contains the required elements."""

    @pytest.fixture
    def spec_text(self) -> str:
        return TLA_SPEC.read_text(encoding="utf-8")

    def test_module_name_is_executor(self, spec_text: str) -> None:
        assert "MODULE executor" in spec_text

    def test_contains_all_states(self, spec_text: str) -> None:
        for state in (
            "PENDING",
            "RUNNING",
            "CHECKPOINTED",
            "COMMIT_INTENT",
            "COMMITTED",
            "COMPLETED",
            "DENIED",
            "FAILED",
            "UNKNOWN",
            "RECONCILING",
            "REVOKED",
            "ESCALATED",
        ):
            assert state in spec_text, f"state {state} missing from spec"

    def test_contains_no_double_effect(self, spec_text: str) -> None:
        assert "NoDoubleEffect" in spec_text

    def test_contains_no_lost_effect(self, spec_text: str) -> None:
        assert "NoLostEffect" in spec_text

    def test_contains_eventual_resolution(self, spec_text: str) -> None:
        assert "EventualResolution" in spec_text

    def test_contains_reconciliation(self, spec_text: str) -> None:
        assert "Reconcile" in spec_text

    def test_contains_revoked(self, spec_text: str) -> None:
        assert "REVOKED" in spec_text
        assert "Revoke" in spec_text

    def test_contains_escalated(self, spec_text: str) -> None:
        assert "ESCALATED" in spec_text
        assert "Escalate" in spec_text

    def test_contains_outbox(self, spec_text: str) -> None:
        assert "outbox" in spec_text

    def test_contains_valid_transition(self, spec_text: str) -> None:
        assert "ValidTransition" in spec_text


class TestTLAConfig:
    """G27.5 — the TLC config file references the required properties."""

    @pytest.fixture
    def cfg_text(self) -> str:
        return TLA_CFG.read_text(encoding="utf-8")

    def test_specifies_spec(self, cfg_text: str) -> None:
        assert "SPECIFICATION" in cfg_text

    def test_checks_no_double_effect(self, cfg_text: str) -> None:
        assert "NoDoubleEffect" in cfg_text

    def test_checks_no_lost_effect(self, cfg_text: str) -> None:
        assert "NoLostEffect" in cfg_text

    def test_checks_eventual_resolution(self, cfg_text: str) -> None:
        assert "EventualResolution" in cfg_text


def _tla2tools_available() -> bool:
    """Check if tla2tools.jar is available for TLC model checking."""
    classpath = os.environ.get("CLASSPATH", "")
    if "tla2tools" in classpath:
        return True
    java = shutil.which("java")
    if java is None:
        return False
    return Path("tla2tools.jar").exists() or FORMAL_DIR.joinpath(
        "tla2tools.jar"
    ).exists()


@pytest.mark.skipif(
    not _tla2tools_available(),
    reason="TLA+ tools (tla2tools.jar) not available; TLC is CI-only",
)
class TestTLCModelCheck:
    """G27.5 — TLC model check finds no violation (CI-only, pinned tools)."""

    def test_tlc_no_violation(self) -> None:
        result = subprocess.run(
            [
                "java",
                "-cp",
                os.environ.get("CLASSPATH", "tla2tools.jar"),
                "tlc2.TLC",
                "-config",
                str(TLA_CFG),
                str(TLA_SPEC),
            ],
            capture_output=True,
            text=True,
            cwd=str(FORMAL_DIR),
            timeout=300,
        )
        assert result.returncode == 0, (
            f"TLC model check failed:\n{result.stdout}\n{result.stderr}"
        )
        assert "No errors" in (result.stdout or "") or (
            "Model checking completed" in (result.stdout or "")
        )
