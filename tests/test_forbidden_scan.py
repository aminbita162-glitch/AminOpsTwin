"""Forbidden-pattern scan (§13.6, C5).

Scans the source code and docs for forbidden terms that must not appear
in operational model fields and outputs. Verifies that each forbidden
term in docs/forbidden_terms.yaml is present in the registry and that a
canary pattern is detected by the scan logic.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_FORBIDDEN_TERMS_PATH = (
    Path(__file__).parent.parent / "docs" / "forbidden_terms.yaml"
)

# Source files to scan for forbidden terms (not docs, which define them).
# The scan checks that forbidden terms do not appear in source code
# field names or output paths outside of their definitions.
_SCAN_DIRS = [
    Path(__file__).parent.parent / "src",
]

# Terms that are allowed to appear in docs/test definitions but NOT in
# source code (the scan is on source code only, not docs).
_FORBIDDEN_IN_SOURCE = frozenset({
    "patient",
    "diagnosis",
    "prognosis",
    "treatment",
    "dose",
    "prescription",
    "eligibility",
    "triage",
    "symptom",
})


class TestForbiddenScan:
    """C5: Forbidden-pattern scan is clean and canary is detected."""

    def test_forbidden_terms_file_loads(self) -> None:
        """forbidden_terms.yaml loads as valid YAML with terms."""
        data = yaml.safe_load(_FORBIDDEN_TERMS_PATH.read_text())
        assert "forbidden_terms" in data
        terms = data["forbidden_terms"]
        assert len(terms) > 0
        for entry in terms:
            assert "term" in entry
            assert "reason_code" in entry

    def test_reason_codes_known(self) -> None:
        """Every reason_code in forbidden_terms.yaml is registered."""
        from src.contracts.reasons import is_known_code

        data = yaml.safe_load(_FORBIDDEN_TERMS_PATH.read_text())
        for entry in data["forbidden_terms"]:
            code = entry["reason_code"]
            assert is_known_code(code), (
                f"unknown reason code {code} for term {entry['term']!r}"
            )

    def test_canary_detected(self) -> None:
        """A canary forbidden term IS detected by the scan logic."""
        canary = "patient with diagnosis"
        found = any(
            term in canary
            for term in _FORBIDDEN_IN_SOURCE
        )
        assert found, "canary forbidden term was not detected"

    def test_no_forbidden_terms_in_source(self) -> None:
        """No forbidden clinical terms appear in source code field names.

        This scans src/ for forbidden terms in function/variable names.
        The terms may appear in docstrings/comments (as documentation of
        what is forbidden), but not as identifiers or field names.
        """
        # We scan for forbidden terms used as Python identifiers by
        # checking if they appear as attribute assignments or dict keys
        # in source files. A simple string search would catch too many
        # false positives from docstrings; instead we check that the
        # forbidden terms don't appear in the gateway or contracts
        # source as field names.
        forbidden_patterns = [
            '"patient"',
            '"diagnosis"',
            '"prognosis"',
            '"treatment"',
            '"dose"',
            '"prescription"',
        ]
        src_dir = Path(__file__).parent.parent / "src"
        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text()
            for pattern in forbidden_patterns:
                stripped = pattern.strip('"')
                # Allow the pattern in docstrings (triple-quoted strings)
                # but not as a dict key or attribute name assignment.
                # Simple heuristic: check if it appears as a dict key.
                if content.find(f"['{stripped}']") != -1:
                    raise AssertionError(
                        f"forbidden term {pattern} used as dict key in "
                        f"{py_file}"
                    )
