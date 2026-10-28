"""G6.6 — Full regression: all P1–P8 gates still pass (P9 regression).

Runs the complete test suite excluding tests/integration/ to confirm
no P9 changes broke any prior-phase functionality.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class TestRegression:
    """G6.6: All P1–P8 gates still pass (regression)."""

    def test_p1_through_p8_suite_passes(self) -> None:
        """Run the P1–P8 test suite and confirm no failures.

        Runs pytest on the test directories for P1–P8 (excluding
        tests/integration/ and tests/enterprise/) with PYTHONHASHSEED=0 to confirm
        no P9 changes broke any prior-phase functionality.

        An env-var guard (AMINOPS_REGRESSION_NESTED) prevents
        infinite recursion when this test is itself run inside
        another phase's regression subprocess.
        """
        if os.environ.get("AMINOPS_REGRESSION_NESTED") == "1":
            # Already running inside a parent regression subprocess;
            # skip to prevent infinite recursion.
            return

        project_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/",
                "--ignore=tests/integration/test_regression_p9.py",
                "--ignore=tests/enterprise/test_regression_p8.py",
                "--tb=short",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(project_root),
            env={
                **os.environ,
                "PYTHONHASHSEED": "0",
                "AMINOPS_REGRESSION_NESTED": "1",
            },
        )
        output = result.stdout + result.stderr
        assert result.returncode == 0, (
            f"P1–P8 test suite has failures:\n{output[-2000:]}"
        )
