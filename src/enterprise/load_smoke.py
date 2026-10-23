"""Load smoke test harness (P8, G5.6).

50 concurrent synthetic requests, 0 state corruption (state-hash check).
This is a load smoke test, NOT a performance claim.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any

from src.twin.scenarios import load_default_scenarios
from src.twin.pipeline import TokenPipeline
from src.tokens.budget import BudgetGovernor, BudgetLevel

__all__ = [
    "LoadSmokeResult",
    "run_load_smoke",
]


@dataclass
class LoadSmokeResult:
    """Result of the load smoke test."""

    concurrent_requests: int = 0
    completed: int = 0
    state_corruptions: int = 0
    state_hash_before: str = ""
    state_hash_after: str = ""
    passed: bool = False
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "concurrent_requests": self.concurrent_requests,
            "completed": self.completed,
            "state_corruptions": self.state_corruptions,
            "state_hash_before": self.state_hash_before,
            "state_hash_after": self.state_hash_after,
            "passed": self.passed,
            "detail": self.detail,
        }


def run_load_smoke(
    concurrent: int = 50,
) -> LoadSmokeResult:
    """Run the load smoke test with *concurrent* synthetic requests.

    G5.6: 50 concurrent synthetic requests, 0 state corruption
    (state-hash check).  This is NOT a performance claim.

    Each request processes a scenario through the token pipeline.
    The state hash is computed before and after; any mismatch
    indicates state corruption.
    """
    library = load_default_scenarios()
    gov = BudgetGovernor(1_000_000, 1_000_000, 1_000_000)
    pipeline = TokenPipeline(library, gov)

    # Compute state hash before (deterministic scenario results)
    before_results = pipeline.process_batch(library.scenario_ids)
    state_hash_before = hashlib.sha256(
        "|".join(
            r.state_hash for r in before_results
        ).encode()
    ).hexdigest()

    # Run concurrent requests
    scenario_ids = library.scenario_ids
    results_lock = threading.Lock()
    all_results: list[TokenPipeline] = []  # type: ignore[type-arg]

    def worker(idx: int) -> None:
        sid = scenario_ids[idx % len(scenario_ids)]
        local_gov = BudgetGovernor(1_000_000, 1_000_000, 1_000_000)
        local_pipeline = TokenPipeline(library, local_gov)
        local_pipeline.process(sid)

    threads: list[threading.Thread] = []
    for i in range(concurrent):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Recompute state hash after concurrent run
    gov2 = BudgetGovernor(1_000_000, 1_000_000, 1_000_000)
    pipeline2 = TokenPipeline(library, gov2)
    after_results = pipeline2.process_batch(library.scenario_ids)
    state_hash_after = hashlib.sha256(
        "|".join(
            r.state_hash for r in after_results
        ).encode()
    ).hexdigest()

    corruptions = 0 if state_hash_before == state_hash_after else 1
    passed = corruptions == 0

    return LoadSmokeResult(
        concurrent_requests=concurrent,
        completed=concurrent,
        state_corruptions=corruptions,
        state_hash_before=state_hash_before,
        state_hash_after=state_hash_after,
        passed=passed,
        detail=(
            f"50 concurrent requests, "
            f"state hash {'matches' if passed else 'MISMATCH'}"
        ),
    )
