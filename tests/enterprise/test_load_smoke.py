"""G5.6 — Load smoke test (P8).

G5.6: 50 concurrent synthetic requests, 0 state corruption
(state-hash check).  This is a load smoke test, NOT a performance
claim.
"""

from __future__ import annotations

from aminopstwin.enterprise.load_smoke import LoadSmokeResult, run_load_smoke


class TestLoadSmoke:
    """G5.6: 50 concurrent requests, 0 state corruption."""

    def test_load_smoke_50_concurrent(self) -> None:
        """50 concurrent requests complete with 0 state corruption."""
        result = run_load_smoke(concurrent=50)
        assert isinstance(result, LoadSmokeResult)
        assert result.concurrent_requests == 50
        assert result.completed == 50
        assert result.state_corruptions == 0
        assert result.passed is True

    def test_state_hash_matches(self) -> None:
        """State hash before and after concurrent run matches."""
        result = run_load_smoke(concurrent=50)
        assert result.state_hash_before == result.state_hash_after
        assert result.state_hash_before != ""

    def test_smaller_concurrent(self) -> None:
        """A smaller concurrent count also passes."""
        result = run_load_smoke(concurrent=10)
        assert result.concurrent_requests == 10
        assert result.completed == 10
        assert result.state_corruptions == 0
        assert result.passed is True

    def test_result_serialization(self) -> None:
        """LoadSmokeResult serializes to dict with required fields."""
        result = run_load_smoke(concurrent=5)
        d = result.to_dict()
        assert "concurrent_requests" in d
        assert "completed" in d
        assert "state_corruptions" in d
        assert "passed" in d
        assert d["state_corruptions"] == 0

    def test_no_performance_claim(self) -> None:
        """The result detail does not claim performance metrics."""
        result = run_load_smoke(concurrent=10)
        # The detail must not claim throughput, latency, or performance
        forbidden = ["throughput", "latency", "requests/sec", "rps"]
        detail_lower = result.detail.lower()
        for word in forbidden:
            assert word not in detail_lower, (
                f"Detail contains forbidden performance claim word: {word}"
            )
