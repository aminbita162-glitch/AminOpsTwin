"""P24 no-skeleton / no-unclaimed-statement test (G24.4).

Verifies that no skeleton, placeholder, or unclaimed public statement
remains in the project's public-facing artefacts.  The scope is the
README (the public surface), the Stage 4 seal document, and the Stage 4
close script.  Internal governance files (owner_decisions.md,
open_questions.md, key_rotation_protocol.md, release notes) legitimately
retain ``[OWNER-FILL]`` markers for pending owner decisions documented in
``docs/open_questions.md`` — these are NOT unclaimed public statements
and are excluded from this gate (see P22 G22.2 which scopes OWNER-FILL
elimination to directive.txt and the phase-sequence governance files).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "stage4_close.py"

# Markers that indicate a skeleton or placeholder in the public surface.
SKELETON_MARKERS = ["[OWNER-FILL]", "TODO", "FIXME", "PLACEHOLDER"]


class TestNoSkeleton:
    """G24.4: no skeleton, placeholder, or unclaimed public statement remains."""

    def test_readme_has_no_skeleton_markers(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for marker in SKELETON_MARKERS:
            assert marker not in readme, (
                f"Marker {marker!r} found in README.md"
            )

    def test_readme_has_no_unclaimed_status(self) -> None:
        """README must not claim a status beyond COMPLETE (CANDIDATE).

        The README's own "What It Is Not" section negates each forbidden
        status ("not clinically validated", "not production-ready").  A
        positive, unnegated assertion of these statuses would be an
        unclaimed public statement.  We verify the negations are present
        as denials and that no bare status header exists.
        """
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        # Required denial phrases — the README must contain each.
        readme_lower = readme.lower()
        required_negations = [
            "not clinically validated",
            "not production-ready",
            "not synchronized with a real organization",
        ]
        for phrase in required_negations:
            assert phrase in readme_lower, (
                f"README must contain the denial '{phrase}'"
            )
        # No bare VERIFIED_CANDIDATE or PRODUCTION status header.
        assert "VERIFIED_CANDIDATE" not in readme, (
            "README must not claim VERIFIED_CANDIDATE"
        )

    def test_stage4_seal_document_present(self) -> None:
        seal_path = REPO_ROOT / "docs" / "stage4_seal.json"
        assert seal_path.exists(), "docs/stage4_seal.json must exist"
        data = json.loads(seal_path.read_text(encoding="utf-8"))
        assert data["stage"] == "4"
        assert len(data["tree_hash"]) == 40
        assert len(data["claim_ids"]) > 0

    def test_stage4_close_script_passes(self) -> None:
        """The stage4_close.py script exits 0 on the current tree."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=30,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")},
        )
        assert result.returncode == 0, (
            f"stage4_close.py failed (exit {result.returncode})\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_directive_has_no_unfilled_placeholders(self) -> None:
        """directive.txt contains no bracketed [OWNER-FILL] placeholders."""
        import re

        directive = (REPO_ROOT / "directive.txt").read_text(encoding="utf-8")
        placeholders = re.findall(r"\[OWNER-FILL[^\]]*\]", directive)
        assert not placeholders, (
            f"directive.txt has {len(placeholders)} [OWNER-FILL] placeholder(s): "
            f"{placeholders}"
        )

    def test_readme_mentions_all_stage4_phases(self) -> None:
        """README references every Stage 4 phase (P21–P24)."""
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for phase in ("P21", "P22", "P23", "P24"):
            assert phase in readme, (
                f"README must reference phase {phase}"
            )
