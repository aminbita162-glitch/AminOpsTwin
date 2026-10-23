"""Adversarial corpus tests (§5.4, G1.3).

Tests that every adversarial corpus entry:
    - has expected_decision DENY
    - has a valid expected_reason_code
    - the corpus has >= 60 cases with the required category distribution
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.contracts.reasons import is_known_code

_CORPUS_PATH = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "adversarial_corpus.json"
)


def _load_corpus() -> list[dict]:
    with _CORPUS_PATH.open() as f:
        data = json.load(f)
    return data.get("corpus", data.get("cases", []))


def _corpus() -> list[dict]:
    return _load_corpus()


class TestAdversarialCorpus:
    """G1.3: Adversarial corpus >= 60 cases, all DENY with reason
    codes."""

    def test_corpus_count(self) -> None:
        """Corpus has >= 60 cases."""
        cases = _corpus()
        assert len(cases) >= 60, (
            f"Need >= 60 cases, got {len(cases)}"
        )

    def test_category_distribution(self) -> None:
        """Category distribution meets minimums."""
        cases = _corpus()
        categories: dict[str, int] = {}
        for c in cases:
            cat = c.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        assert categories.get("CLIN", 0) >= 25, (
            f"Need >= 25 CLIN, got {categories.get('CLIN', 0)}"
        )
        assert categories.get("INJ", 0) >= 15, (
            f"Need >= 15 INJ, got {categories.get('INJ', 0)}"
        )
        assert categories.get("SCHEMA", 0) >= 10, (
            f"Need >= 10 SCHEMA, got {categories.get('SCHEMA', 0)}"
        )
        assert categories.get("AUTH", 0) >= 5, (
            f"Need >= 5 AUTH, got {categories.get('AUTH', 0)}"
        )
        assert categories.get("IDEM", 0) >= 5, (
            f"Need >= 5 IDEM, got {categories.get('IDEM', 0)}"
        )

    @pytest.mark.parametrize("case", _corpus())
    def test_all_denied(self, case: dict) -> None:
        """Every case has expected_decision DENY."""
        assert case["expected_decision"] == "DENY", (
            f"{case['id']}: expected DENY, "
            f"got {case['expected_decision']}"
        )

    @pytest.mark.parametrize("case", _corpus())
    def test_all_have_reason_code(self, case: dict) -> None:
        """Every case has a valid reason_code."""
        assert case.get("expected_reason_code"), (
            f"{case['id']}: missing expected_reason_code"
        )

    @pytest.mark.parametrize("case", _corpus())
    def test_reason_code_known(self, case: dict) -> None:
        """Every reason_code is in the reason code registry."""
        code = case["expected_reason_code"]
        assert is_known_code(code), (
            f"{case['id']}: unknown reason code {code}"
        )

    @pytest.mark.parametrize("case", _corpus())
    def test_required_fields(self, case: dict) -> None:
        """Every case has the required fields."""
        required = {
            "id",
            "corpus_version",
            "category",
            "input",
            "expected_decision",
            "expected_reason_code",
            "rationale",
            "added_in_phase",
        }
        missing = required - set(case.keys())
        assert not missing, (
            f"{case.get('id', '?')}: missing fields {missing}"
        )
