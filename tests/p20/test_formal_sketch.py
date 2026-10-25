"""P20 formal sketch test (G20.1).

Verifies that the formal gateway properties document exists and
references concrete code locations.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
SKETCH_PATH = REPO_ROOT / "docs" / "formal" / "gateway_properties.md"


class TestFormalSketch:
    """G20.1: formal sketch present and references concrete code."""

    def test_document_exists(self) -> None:
        """The formal sketch document exists."""
        assert SKETCH_PATH.exists(), (
            f"Formal sketch not found at {SKETCH_PATH}"
        )

    def test_document_has_required_sections(self) -> None:
        """The document contains the required property sections."""
        content = SKETCH_PATH.read_text(encoding="utf-8")
        required_sections = [
            "Deny-by-default",
            "No Gateway state leakage",
            "Rejection of non-aggregate payloads",
            "Deterministic replay identity",
            "Quota enforcement",
        ]
        for section in required_sections:
            assert section in content, (
                f"Missing required section: {section!r}"
            )

    def test_document_references_concrete_code_locations(self) -> None:
        """The document references concrete source file paths."""
        content = SKETCH_PATH.read_text(encoding="utf-8")
        # Must reference at least 3 concrete source file paths.
        code_refs = re.findall(
            r"src/aminopstwin/[a-z_]+/[a-z_]+\.py(?::\d+)?",
            content,
        )
        assert len(code_refs) >= 3, (
            f"Expected >= 3 concrete code references, found {len(code_refs)}: "
            f"{code_refs}"
        )

    def test_document_has_references_table(self) -> None:
        """The document has a references table mapping properties to code."""
        content = SKETCH_PATH.read_text(encoding="utf-8")
        assert "| Property" in content
        assert "| Code location" in content
        assert "| Test" in content

    def test_document_references_test_gates(self) -> None:
        """The document references gate IDs as test evidence."""
        content = SKETCH_PATH.read_text(encoding="utf-8")
        gate_refs = re.findall(r"G\d+\.\d+", content)
        assert len(gate_refs) >= 3, (
            f"Expected >= 3 gate references, found {len(gate_refs)}"
        )
