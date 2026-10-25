"""P15 full regression test (G15.6).

Runs the full test suite (excluding P15's own regression test to
avoid infinite recursion) and verifies that all tests pass.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

NESTED_GUARD = "AMINOPS_REGRESSION_NESTED_P15"


class TestFullRegression:
    """G15.6: full regression 0 failures."""

    def test_full_regression_passes(self) -> None:
        """Run the full test suite (excluding this file) and verify 0 failures."""
        if os.environ.get(NESTED_GUARD):
            pytest.skip("nested regression guard — P15")

        env = {**os.environ, "PYTHONHASHSEED": "0", NESTED_GUARD: "1"}
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                str(REPO_ROOT / "tests"),
                "-q",
                "--tb=short",
                "--no-header",
                "-p",
                "no:cacheprovider",
                "--no-cov",
                "--ignore",
                str(REPO_ROOT / "tests" / "p15" / "test_regression.py"),
                "--ignore",
                str(REPO_ROOT / "tests" / "p14" / "test_regression.py"),
                "--ignore",
                str(REPO_ROOT / "tests" / "p16"),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=1800,
            cwd=str(REPO_ROOT),
        )

        lines = result.stdout.strip().split("\n")
        summary_line = ""
        for line in lines:
            if "passed" in line or "failed" in line or "error" in line:
                summary_line = line
                break

        assert result.returncode == 0, (
            f"full regression failed (exit {result.returncode})\n"
            f"Summary: {summary_line}\n"
            f"stdout:\n{result.stdout[-2000:]}\n"
            f"stderr:\n{result.stderr[-1000:]}"
        )

        assert "failed" not in summary_line or "0 failed" in summary_line, (
            f"tests failed in full regression\n{summary_line}"
        )
