"""Full token pipeline for P3 (G3.5).

Integrates the pre-filter (§4.1), Policy Gateway, evidence cache,
invariant check, and budget governor into a unified pipeline that
processes simulation requests. The pipeline resolves as many
requests as possible with 0 LLM tokens by using the deterministic
simulation engine directly.

Token accounting:
    - A request that is served from the cache uses 0 LLM tokens.
    - A request that is served by the deterministic simulation
      engine uses 0 LLM tokens.
    - A request that requires LLM assistance uses budgeted tokens.
    - The target is >= 40% of requests resolved with 0 LLM tokens
      [OWNER-CONFIRM; calibrate from G2.6].
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from src.tokens.budget import BudgetGovernor, BudgetLevel
from src.tokens.fallback import FallbackReason
from src.tokens.prefilter import PreFilterStage
from src.twin.scenarios import ScenarioLibrary

__all__ = [
    "PipelineResult",
    "TokenPipeline",
]


@dataclass
class PipelineResult:
    """Result of a single pipeline run for one request."""

    scenario_id: str
    tokens_used: int = 0
    tokens_reserved: int = 0
    cache_hit: bool = False
    zero_token: bool = True
    path: str = "deterministic"
    pre_filter_stages: list[str] = field(default_factory=list)
    state_hash: str = ""
    budget_level: str = ""
    fallback_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "tokens_used": self.tokens_used,
            "tokens_reserved": self.tokens_reserved,
            "cache_hit": self.cache_hit,
            "zero_token": self.zero_token,
            "path": self.path,
            "pre_filter_stages": list(self.pre_filter_stages),
            "state_hash": self.state_hash,
            "budget_level": self.budget_level,
            "fallback_reason": self.fallback_reason,
        }


class TokenPipeline:
    """Full token pipeline integrating pre-filter, cache, budget, and
    simulation (G3.5).

    The pipeline processes each request through the fixed pre-filter
    order (§4.1):
        SCHEMA → GATEWAY → CACHE → INVARIANT → BUDGET → OUTPUT

    Requests that can be served by the deterministic simulation
    engine (i.e. all standard simulation requests) use 0 LLM tokens.
    """

    def __init__(
        self,
        library: ScenarioLibrary,
        governor: BudgetGovernor,
        cache: dict[str, str] | None = None,
    ) -> None:
        self._library = library
        self._governor = governor
        self._cache: dict[str, str] = cache if cache is not None else {}
        self._prefilter_order = [
            PreFilterStage.SCHEMA,
            PreFilterStage.GATEWAY,
            PreFilterStage.CACHE,
            PreFilterStage.INVARIANT,
            PreFilterStage.BUDGET,
            PreFilterStage.OUTPUT,
        ]

    def process(
        self,
        scenario_id: str,
        correlation_id: uuid.UUID | None = None,
        policy_epoch: int = 0,
    ) -> PipelineResult:
        """Process a single request through the full pipeline."""
        if correlation_id is None:
            correlation_id = uuid.uuid4()

        result = PipelineResult(
            scenario_id=scenario_id,
            pre_filter_stages=[
                s.value for s in self._prefilter_order
            ],
        )

        # --- Stage 1: SCHEMA ---
        sc = self._library.get(scenario_id)
        if sc is None:
            result.path = "deterministic"
            result.zero_token = True
            result.fallback_reason = "schema_not_found"
            return result

        # --- Stage 2: GATEWAY ---
        # In P3, all registered scenarios pass the gateway (single-tenant).
        # The gateway check is a no-op for deterministic scenarios.

        # --- Stage 3: CACHE ---
        cache_key = f"{scenario_id}:{sc.seed}:{sc.sim_duration}"
        cached_hash = self._cache.get(cache_key)
        if cached_hash is not None:
            result.cache_hit = True
            result.zero_token = True
            result.state_hash = cached_hash
            result.path = "deterministic"
            result.tokens_used = 0
            return result

        # --- Stage 4: INVARIANT ---
        # Check basic invariants (all capacities > 0, etc.)
        if sc.capacity_per_resource <= 0 or sc.queue_capacity <= 0:
            result.zero_token = True
            result.fallback_reason = "invariant_failed"
            return result

        # --- Stage 5: BUDGET ---
        # Reserve tokens for a potential LLM call (even though we
        # may not need them; the reservation is released after).
        reserved = 100
        if self._governor.is_exhausted(BudgetLevel.WORKFLOW):
            fallback = self._governor.get_fallback(
                correlation_id=correlation_id,
                policy_epoch=policy_epoch,
                reason=FallbackReason.BUDGET_WORKFLOW_EXHAUSTED,
            )
            result.path = "deterministic"
            result.zero_token = True
            result.tokens_used = 0
            result.fallback_reason = str(fallback.fallback_reason)
            result.budget_level = BudgetLevel.WORKFLOW.value
            return result

        ok = self._governor.reserve(
            BudgetLevel.WORKFLOW, reserved
        )
        result.tokens_reserved = reserved if ok else 0
        result.budget_level = BudgetLevel.WORKFLOW.value

        # --- Stage 6: OUTPUT ---
        # Run the deterministic simulation (uses 0 LLM tokens)
        sim_result = self._library.run(scenario_id)
        # Release the reserved tokens (we didn't use them)
        if ok:
            self._governor.reconcile(
                BudgetLevel.WORKFLOW, reserved, 0
            )

        result.state_hash = sim_result.final_state_hash
        result.zero_token = True
        result.tokens_used = 0
        result.path = "deterministic"

        # Cache the result
        self._cache[cache_key] = sim_result.final_state_hash

        return result

    def process_batch(
        self,
        scenario_ids: list[str],
        policy_epoch: int = 0,
    ) -> list[PipelineResult]:
        """Process a batch of requests and return results."""
        return [
            self.process(sid, policy_epoch=policy_epoch)
            for sid in scenario_ids
        ]

    def benchmark(
        self,
        policy_epoch: int = 0,
    ) -> dict[str, Any]:
        """Run the full benchmark on all scenarios in the library.

        Returns a dict with benchmark metrics (G3.5):
            - total_requests
            - zero_token_requests
            - zero_token_rate
            - cache_hits
            - cache_hit_rate
            - tokens_per_capability
        """
        scenario_ids = self._library.scenario_ids
        results = self.process_batch(scenario_ids, policy_epoch)

        total = len(results)
        zero_token = sum(1 for r in results if r.zero_token)
        cache_hits = sum(1 for r in results if r.cache_hit)

        # Tokens per capability: aggregate tokens_used per scenario_id
        tokens_per_cap: dict[str, int] = {}
        for r in results:
            tokens_per_cap[r.scenario_id] = r.tokens_used

        return {
            "total_requests": total,
            "zero_token_requests": zero_token,
            "zero_token_rate": (
                zero_token / total if total > 0 else 0.0
            ),
            "cache_hits": cache_hits,
            "cache_hit_rate": (
                cache_hits / total if total > 0 else 0.0
            ),
            "tokens_per_capability": tokens_per_cap,
        }
