"""Tests for P26 deliverable 1: ADR schema validation (G26.2).

ADR-002 to ADR-008 exist, have status Accepted, and pass a schema lint.
"""

from __future__ import annotations

import os
import re

import pytest

_ADR_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "docs", "adr"
)


def _adr_files() -> list[str]:
    """Return the list of ADR files that must exist (ADR-002 to ADR-008)."""
    return [
        "ADR-002-licence.md",
        "ADR-003-revocation.md",
        "ADR-004-idempotency.md",
        "ADR-005-audit-anchoring.md",
        "ADR-006-unknown-outcomes.md",
        "ADR-007-authority-precedence.md",
        "ADR-008-sovereign-by-design.md",
    ]


@pytest.mark.parametrize("filename", _adr_files())
def test_adr_exists(filename: str) -> None:
    """Each ADR file exists."""
    path = os.path.join(_ADR_DIR, filename)
    assert os.path.isfile(path), f"Missing ADR: {filename}"


@pytest.mark.parametrize("filename", _adr_files())
def test_adr_has_status_accepted(filename: str) -> None:
    """Each ADR has '## Status' section with 'Accepted'."""
    path = os.path.join(_ADR_DIR, filename)
    with open(path) as f:
        content = f.read()
    assert re.search(r"^##\s+Status", content, re.MULTILINE), (
        f"{filename} missing '## Status' section"
    )
    assert "Accepted" in content, (
        f"{filename} missing 'Accepted' status"
    )


@pytest.mark.parametrize("filename", _adr_files())
def test_adr_has_context_and_decision(filename: str) -> None:
    """Each ADR has Context and Decision sections."""
    path = os.path.join(_ADR_DIR, filename)
    with open(path) as f:
        content = f.read()
    assert re.search(r"^##\s+Context", content, re.MULTILINE), (
        f"{filename} missing '## Context' section"
    )
    assert re.search(r"^##\s+Decision", content, re.MULTILINE), (
        f"{filename} missing '## Decision' section"
    )


@pytest.mark.parametrize("filename", _adr_files())
def test_adr_has_consequences(filename: str) -> None:
    """Each ADR has Consequences section."""
    path = os.path.join(_ADR_DIR, filename)
    with open(path) as f:
        content = f.read()
    assert re.search(r"^##\s+Consequences", content, re.MULTILINE), (
        f"{filename} missing '## Consequences' section"
    )


@pytest.mark.parametrize("filename", _adr_files())
def test_adr_has_proof_tests(filename: str) -> None:
    """Each ADR has proof tests section."""
    path = os.path.join(_ADR_DIR, filename)
    with open(path) as f:
        content = f.read()
    assert re.search(r"^##\s+Proof\s+tests", content, re.MULTILINE), (
        f"{filename} missing '## Proof tests' section"
    )


@pytest.mark.parametrize("filename", _adr_files())
def test_adr_no_owner_fill(filename: str) -> None:
    """No ADR contains [OWNER-FILL] markers."""
    path = os.path.join(_ADR_DIR, filename)
    with open(path) as f:
        content = f.read()
    assert "[OWNER-FILL]" not in content, (
        f"{filename} contains [OWNER-FILL] marker"
    )
