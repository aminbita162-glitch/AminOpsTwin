"""Pre-filter order unit test (§4.1, G1.9)."""

from __future__ import annotations

from src.tokens.prefilter import (
    PREFILTER_ORDER,
    PreFilterStage,
    prefilter_order_valid,
)


class TestPreFilterOrder:
    """G1.9: Pre-filter order is fixed and tested."""

    def test_order_matches_expected(self) -> None:
        """The pre-filter order matches the directive's fixed order."""
        assert PREFILTER_ORDER == (
            PreFilterStage.SCHEMA,
            PreFilterStage.GATEWAY,
            PreFilterStage.CACHE,
            PreFilterStage.INVARIANT,
            PreFilterStage.BUDGET,
            PreFilterStage.OUTPUT,
        )

    def test_order_valid(self) -> None:
        """The pre-filter order passes the validity check."""
        assert prefilter_order_valid(
            list(PREFILTER_ORDER)
        )

    def test_reordered_invalid(self) -> None:
        """A reordered pre-filter list is invalid."""
        reordered = [
            PreFilterStage.GATEWAY,
            PreFilterStage.SCHEMA,
            PreFilterStage.CACHE,
            PreFilterStage.INVARIANT,
            PreFilterStage.BUDGET,
            PreFilterStage.OUTPUT,
        ]
        assert not prefilter_order_valid(reordered)

    def test_truncated_invalid(self) -> None:
        """A truncated pre-filter list is invalid."""
        truncated = list(PREFILTER_ORDER)[:5]
        assert not prefilter_order_valid(truncated)

    def test_extra_invalid(self) -> None:
        """An extra stage makes the list invalid."""
        extra = list(PREFILTER_ORDER) + [PreFilterStage.SCHEMA]
        assert not prefilter_order_valid(extra)

    def test_six_stages(self) -> None:
        """The pre-filter has exactly six stages."""
        assert len(PREFILTER_ORDER) == 6

    def test_no_duplicates(self) -> None:
        """No duplicate stages in the order."""
        assert len(set(PREFILTER_ORDER)) == len(PREFILTER_ORDER)
