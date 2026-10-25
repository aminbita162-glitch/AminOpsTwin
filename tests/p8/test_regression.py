"""G5.7 — All P1–P7 gates still pass (regression, P8).

G5.7: Full regression — the complete P1–P7 test suite passes
with no new failures.  This is the regression gate for P8.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


class TestRegression:
    """G5.7: All P1–P7 gates still pass (regression)."""

    def test_p1_through_p7_suite_passes(self) -> None:
        """Run the P1–P7 test suite and confirm no failures.

        Runs pytest on the test directories for P1–P7 (excluding
        tests/p8/) with PYTHONHASHSEED=0 to confirm no P8 changes
        broke any prior-phase functionality.

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
                "--ignore=tests/p8",
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
            f"P1–P7 test suite has failures:\n{output[-2000:]}"
        )
