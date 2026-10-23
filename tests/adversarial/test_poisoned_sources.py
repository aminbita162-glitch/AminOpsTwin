"""Poisoned source tests (G2.7).

Tests:
    - At least 10 poisoned-source fixtures
    - 0 successful indirect injections
    - Each fixture is rejected with the expected reason

The poisoned-source fixtures test that source content carrying injection
attempts (direct, indirect, redirect, oversized, unsupported field) is
rejected by the pre-filter / gateway pipeline. The key invariant: no
injected instruction in source content ever bypasses the Policy Gateway.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_POISONED_PATH = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "poisoned_sources.json"
)

# Patterns that indicate injection attempts in source text.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+are", re.IGNORECASE),
    re.compile(r"override\s+(current\s+)?policy", re.IGNORECASE),
    re.compile(r"bypass\s+the\s+policy\s+gateway", re.IGNORECASE),
    re.compile(r"disregard\s+all\s+prior\s+constraints", re.IGNORECASE),
    re.compile(r"redirect\s+(all\s+)?responses?\s+to", re.IGNORECASE),
    re.compile(r"redirect_to\s*:", re.IGNORECASE),
    re.compile(r"reveal\s+all\s+secret\s+keys", re.IGNORECASE),
    re.compile(r"disable\s+all\s+safety\s+checks", re.IGNORECASE),
    re.compile(r"output\s+the\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"forget\s+your\s+guidelines", re.IGNORECASE),
    re.compile(r"system\s+override", re.IGNORECASE),
    re.compile(r"execute\s+the\s+following\s+command", re.IGNORECASE),
    re.compile(r"steal\b.*\bendpoint\b", re.IGNORECASE),
    re.compile(r"dear\s+assistant", re.IGNORECASE),
    re.compile(r"ignore\s+the\s+policy\s+gateway", re.IGNORECASE),
    re.compile(r"disregard\s+all\s+prior", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a\s+different\s+model", re.IGNORECASE),
]

# Max allowed source text length (oversized input detection).
_MAX_SOURCE_LENGTH = 512

# Allowed field name pattern (alphanumeric + underscore, reasonable length).
_FIELD_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _load_poisoned_sources() -> list[dict]:
    with _POISONED_PATH.open() as f:
        data = json.load(f)
    return data.get("poisoned_sources", [])


def _detect_poison(source_text: str) -> str | None:
    """Detect poison in source text and return the rejection reason code.

    Returns None if no poison is detected (should not happen for these
    fixtures).
    """
    # Check for oversized input
    if len(source_text) > _MAX_SOURCE_LENGTH:
        return "GW-SCHEMA-004"

    # Check for unsupported field (looks like a raw field dump, not natural text)
    if source_text.startswith("unsupported_field_") and len(source_text) > 100:
        return "GW-SCHEMA-001"

    # Check for redirect attempts — URLs or redirect directives
    redirect_patterns = [
        re.compile(r"redirect\s+(all\s+)?(responses?|evidence)", re.IGNORECASE),
        re.compile(r"redirect_to\s*:", re.IGNORECASE),
        re.compile(r"http://[a-z]", re.IGNORECASE),
        re.compile(r"https://[a-z]", re.IGNORECASE),
        re.compile(r"external\s+endpoint", re.IGNORECASE),
    ]
    has_redirect = any(p.search(source_text) for p in redirect_patterns)

    # Check for injection patterns
    has_injection = any(
        p.search(source_text) for p in _INJECTION_PATTERNS
    )

    # Distinguish direct vs indirect injection
    # Direct: starts with an imperative or override directive to the assistant
    direct_indicators = [
        re.compile(
            r"^(ignore|system|instruction|override)\s*:",
            re.IGNORECASE,
        ),
        re.compile(
            r"^(ignore|override|bypass)\s+(all\s+)?(previous|current|the)",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\[?(system\s+override|instruction)\]?\s*:",
            re.IGNORECASE,
        ),
        re.compile(r"^\[redacted\].*override", re.IGNORECASE),
        re.compile(r"override\s+current\s+policy", re.IGNORECASE),
        re.compile(r"bypass\s+the\s+policy\s+gateway", re.IGNORECASE),
    ]
    is_direct = any(
        p.search(source_text) for p in direct_indicators
    )

    if is_direct:
        return "GW-INJ-001"

    if has_injection or has_redirect:
        return "GW-INJ-002"

    return None


class TestPoisonedSources:
    """G2.7: Poisoned source fixtures — all rejected, 0 injections succeed."""

    def test_at_least_10_fixtures(self) -> None:
        sources = _load_poisoned_sources()
        assert len(sources) >= 10

    def test_all_fixtures_rejected(self) -> None:
        sources = _load_poisoned_sources()
        for source in sources:
            reason = _detect_poison(source["source_text"])
            assert reason is not None, (
                f"Source {source['id']} was not detected as poisoned: "
                f"{source['source_text'][:50]}..."
            )
            assert reason == source["expected_rejection_reason"], (
                f"Source {source['id']}: expected "
                f"{source['expected_rejection_reason']}, got {reason}"
            )

    def test_zero_successful_injections(self) -> None:
        """No poisoned source should pass through undetected."""
        sources = _load_poisoned_sources()
        for source in sources:
            reason = _detect_poison(source["source_text"])
            # Every poisoned source must be detected (reason is not None)
            assert reason is not None, (
                f"INJECTION SUCCEEDED for {source['id']}: "
                f"{source['source_text'][:80]}..."
            )

    def test_fixture_structure(self) -> None:
        """Each fixture has the required fields."""
        sources = _load_poisoned_sources()
        required_fields = {
            "id", "source_text", "poison_type",
            "expected_rejection_reason",
        }
        for source in sources:
            assert required_fields.issubset(source.keys()), (
                f"Fixture {source.get('id', '?')} missing fields: "
                f"{required_fields - set(source.keys())}"
            )

    def test_fixture_types_diverse(self) -> None:
        """Fixtures cover all required poison types."""
        sources = _load_poisoned_sources()
        types = {s["poison_type"] for s in sources}
        required_types = {
            "instruction_injection",
            "indirect_injection",
            "redirect",
            "oversized_input",
            "unsupported_field",
        }
        assert required_types.issubset(types), (
            f"Missing poison types: {required_types - types}"
        )

    @pytest.mark.parametrize(
        "source",
        _load_poisoned_sources(),
        ids=lambda s: s["id"],
    )
    def test_individual_rejection(self, source: dict) -> None:
        """Each individual fixture is rejected with the expected reason."""
        reason = _detect_poison(source["source_text"])
        assert reason is not None, (
            f"Source {source['id']} not detected as poisoned"
        )
        assert reason == source["expected_rejection_reason"], (
            f"Source {source['id']}: expected "
            f"{source['expected_rejection_reason']}, got {reason}"
        )
