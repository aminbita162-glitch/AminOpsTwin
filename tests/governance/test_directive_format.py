"""Directive format governance test (G25.1).

Verifies that the CURRENT directive.txt follows the expected structure:
  - The [DEV-AGENT] box is present at the top of the file.
  - Every phase card P25 to P34 exists with the required sections:
    STATUS, OBJECTIVE, PRECONDITIONS, INPUTS, ALLOWED PATHS,
    FORBIDDEN PATHS, DELIVERABLES, and GATES.
  - No unfilled placeholder (bracketed OWNER-FILL, TODO, or TBD marker)
    is present in the directive.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DIRECTIVE = REPO_ROOT / "directive.txt"

REQUIRED_SECTIONS = [
    "STATUS",
    "OBJECTIVE",
    "PRECONDITIONS",
    "INPUTS",
    "ALLOWED PATHS",
    "FORBIDDEN PATHS",
    "DELIVERABLES",
    "GATES",
]

REQUIRED_PHASES = [f"P{i}" for i in range(25, 35)]


class TestDirectiveFormat:
    """G25.1: directive.txt has the correct structure and no placeholders."""

    def test_directive_exists(self) -> None:
        assert DIRECTIVE.exists(), "directive.txt must exist"

    def test_dev_agent_box_present(self) -> None:
        """The [DEV-AGENT] box is present at the top of directive.txt."""
        content = DIRECTIVE.read_text()
        assert "[DEV-AGENT]" in content, (
            "directive.txt must contain the [DEV-AGENT] execution charter box"
        )

    def test_all_phase_cards_present(self) -> None:
        """Every phase card P25 to P34 exists in directive.txt."""
        content = DIRECTIVE.read_text()
        for phase in REQUIRED_PHASES:
            pattern = f"PHASE {phase} "
            assert pattern in content, (
                f"directive.txt must define phase card for {phase}"
            )

    def test_all_phase_sections_present(self) -> None:
        """Every phase card P25 to P34 has all required sections."""
        content = DIRECTIVE.read_text()
        for phase in REQUIRED_PHASES:
            # Find the phase card and the next phase card or end
            start = content.find(f"PHASE {phase} ")
            if start == -1:
                continue
            # Find the next phase card or end of file
            next_phase = None
            for p in REQUIRED_PHASES:
                if p == phase:
                    continue
                idx = content.find(f"PHASE {p} ", start + 1)
                if idx != -1:
                    if next_phase is None or idx < next_phase:
                        next_phase = idx
            if next_phase is None:
                # Check for END OF DIRECTIVE
                end_idx = content.find("END OF DIRECTIVE", start + 1)
                end = end_idx if end_idx != -1 else len(content)
            else:
                end = next_phase
            card = content[start:end]
            for section in REQUIRED_SECTIONS:
                assert section in card, (
                    f"Phase {phase} is missing section '{section}'"
                )

    def test_no_unfilled_placeholders(self) -> None:
        """No bracketed OWNER-FILL, TODO, or TBD placeholder is present."""
        content = DIRECTIVE.read_text()
        placeholders: list[str] = []
        placeholders.extend(re.findall(r"\[OWNER-FILL[^\]]*\]", content))
        placeholders.extend(re.findall(r"\[TODO[^\]]*\]", content))
        placeholders.extend(re.findall(r"\[TBD[^\]]*\]", content))
        assert not placeholders, (
            f"directive.txt contains {len(placeholders)} unfilled "
            f"placeholder(s): {placeholders}"
        )
