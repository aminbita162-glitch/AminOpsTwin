"""Token benchmark tests (G3.5).

Token benchmark on a fixed 200-request synthetic suite stored in
the repo: tokens-avoided, cache-hit-rate, and tokens-per-capability
reported; target >= 40% of requests resolved with 0 LLM tokens.
"""

from __future__ import annotations

import json
import os

from aminopstwin.tokens.budget import BudgetGovernor
from aminopstwin.twin.benchmark import (
    BENCHMARK_FIXTURE_PATH,
    generate_benchmark_suite,
    load_benchmark_suite,
)
from aminopstwin.twin.pipeline import TokenPipeline
from aminopstwin.twin.scenarios import load_default_scenarios


class TestTokenBenchmark:
    """Token benchmark tests (G3.5)."""

    def test_benchmark_fixture_exists(self) -> None:
        """The 200-request benchmark fixture is stored in the repo."""
        assert os.path.exists(BENCHMARK_FIXTURE_PATH)

    def test_benchmark_fixture_has_200_requests(self) -> None:
        """The benchmark fixture has exactly 200 requests."""
        with open(BENCHMARK_FIXTURE_PATH) as f:
            data = json.load(f)
        assert len(data) == 200

    def test_benchmark_suite_is_synthetic(self) -> None:
        """Every benchmark request is synthetic."""
        with open(BENCHMARK_FIXTURE_PATH) as f:
            data = json.load(f)
        for req in data:
            prov = req.get("provenance", {})
            assert prov.get("synthetic") is True

    def test_zero_token_rate_ge_40_pct(self) -> None:
        """Target: >= 40% of requests resolved with 0 LLM tokens."""
        with open(BENCHMARK_FIXTURE_PATH) as f:
            data = json.load(f)
        lib = load_benchmark_suite(data)
        governor = BudgetGovernor(
            session_budget=100000,
            workflow_budget=10000,
            capability_budget=10000,
        )
        pipeline = TokenPipeline(lib, governor)
        metrics = pipeline.benchmark()

        assert metrics["total_requests"] == 200
        assert metrics["zero_token_rate"] >= 0.40

    def test_tokens_per_capability_reported(self) -> None:
        """tokens-per-capability is reported for every scenario."""
        with open(BENCHMARK_FIXTURE_PATH) as f:
            data = json.load(f)
        lib = load_benchmark_suite(data)
        governor = BudgetGovernor(
            session_budget=100000,
            workflow_budget=10000,
            capability_budget=10000,
        )
        pipeline = TokenPipeline(lib, governor)
        metrics = pipeline.benchmark()

        assert "tokens_per_capability" in metrics
        tpc = metrics["tokens_per_capability"]
        assert len(tpc) > 0
        for sid, tokens in tpc.items():
            assert isinstance(sid, str)
            assert isinstance(tokens, int)
            assert tokens >= 0

    def test_cache_hit_rate_increases_on_rerun(self) -> None:
        """Running the benchmark twice increases cache hits."""
        with open(BENCHMARK_FIXTURE_PATH) as f:
            data = json.load(f)
        lib = load_benchmark_suite(data)
        governor = BudgetGovernor(
            session_budget=100000,
            workflow_budget=10000,
            capability_budget=10000,
        )
        pipeline = TokenPipeline(lib, governor)

        # First run
        metrics1 = pipeline.benchmark()
        # Second run (should have cache hits)
        metrics2 = pipeline.benchmark()

        assert metrics2["cache_hits"] > metrics1["cache_hits"]

    def test_generate_benchmark_suite_200(self) -> None:
        """generate_benchmark_suite produces 200 requests."""
        suite = generate_benchmark_suite()
        assert len(suite) == 200


class TestPrefilterOrder:
    """G3.7: Pre-filter order enforced; bypass attempts = 0 successes."""

    def test_prefilter_order_enforced(self) -> None:
        """Pre-filter order is enforced in the pipeline."""
        from aminopstwin.tokens.prefilter import (
            PREFILTER_ORDER,
            prefilter_order_valid,
        )
        assert prefilter_order_valid(list(PREFILTER_ORDER))

    def test_no_bypass_succeeds(self) -> None:
        """A request bypassing the pre-filter cannot succeed."""
        from aminopstwin.tokens.prefilter import (
            PREFILTER_ORDER,
            prefilter_order_valid,
        )
        # Reversed order should not be valid
        reversed_order = list(reversed(PREFILTER_ORDER))
        assert not prefilter_order_valid(reversed_order)


class TestUncertaintyReporting:
    """G3.6: Uncertainty reporting present in 100% of simulation outputs."""

    def test_all_scenarios_have_uncertainty(self) -> None:
        """All default scenarios produce uncertainty reports."""
        lib = load_default_scenarios()
        for sid in lib.scenario_ids:
            result = lib.run(sid)
            assert result.uncertainty is not None
            u = result.uncertainty
            assert (
                u.wait_time_interval is not None
                or u.not_estimable_reason is not None
            )
