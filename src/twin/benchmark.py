"""200-request synthetic benchmark suite for token efficiency (G3.5).

A fixed set of 200 synthetic requests stored in the repo. Each
request is a ScenarioConfig that can be run deterministically. The
benchmark measures:
    - tokens-avoided: requests resolved with 0 LLM tokens
    - cache-hit-rate: requests served from the evidence cache
    - tokens-per-capability: tokens consumed per capability
"""

from __future__ import annotations

import json
from typing import Any

from src.twin.scenarios import Scenario, ScenarioLibrary

__all__ = [
    "BENCHMARK_FIXTURE_PATH",
    "generate_benchmark_suite",
    "load_benchmark_suite",
    "BenchmarkResult",
]

BENCHMARK_FIXTURE_PATH: str = "fixtures/benchmark_suite_200.json"


def generate_benchmark_suite() -> list[dict[str, Any]]:
    """Generate 200 synthetic benchmark requests.

    Each request is a serialised ScenarioConfig with provenance.
    """
    requests: list[dict[str, Any]] = []
    provenance: dict[str, Any] = {
        "synthetic": True,
        "generator_id": "aminopstwin-fixtures-gen-v1",
        "generator_version": "0.1.0",
        "seed": 0,
    }
    for i in range(200):
        seed = i
        num_sites = (i % 3) + 1
        num_resources = (i % 4) + 2
        num_queues = (i % 2) + 1
        capacity = (i % 5) + 3
        queue_cap = (i % 10) * 10 + 50
        arrival_rate = float((i % 5) + 1)
        mean_service = (i % 8) + 2
        sim_duration = 20 + (i % 30)
        requests.append(
            {
                "scenario_id": f"bench-{i:04d}",
                "seed": seed,
                "num_sites": num_sites,
                "num_resources_per_site": num_resources,
                "num_queues_per_site": num_queues,
                "capacity_per_resource": capacity,
                "queue_capacity": queue_cap,
                "arrival_rate": arrival_rate,
                "mean_service_time": mean_service,
                "sim_duration": sim_duration,
                "description": f"Benchmark request {i}",
                "provenance": provenance,
            }
        )
    return requests


def load_benchmark_suite(
    data: list[dict[str, Any]] | None = None,
) -> ScenarioLibrary:
    """Load the 200-request benchmark suite into a ScenarioLibrary."""
    if data is None:
        data = generate_benchmark_suite()
    lib = ScenarioLibrary()
    for req in data:
        lib.add(
            Scenario(
                scenario_id=req["scenario_id"],
                seed=req["seed"],
                num_sites=req["num_sites"],
                num_resources_per_site=req[
                    "num_resources_per_site"
                ],
                num_queues_per_site=req["num_queues_per_site"],
                capacity_per_resource=req["capacity_per_resource"],
                queue_capacity=req["queue_capacity"],
                arrival_rate=req["arrival_rate"],
                mean_service_time=req["mean_service_time"],
                sim_duration=req["sim_duration"],
                description=req["description"],
                provenance=req.get("provenance", {}),
            )
        )
    return lib


class BenchmarkResult:
    """Result of running the token benchmark suite (G3.5)."""

    def __init__(
        self,
        total_requests: int,
        zero_token_requests: int,
        cache_hits: int,
        tokens_per_capability: dict[str, int],
    ) -> None:
        self.total_requests = total_requests
        self.zero_token_requests = zero_token_requests
        self.cache_hits = cache_hits
        self.tokens_per_capability = tokens_per_capability

    @property
    def zero_token_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.zero_token_requests / self.total_requests

    @property
    def cache_hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "zero_token_requests": self.zero_token_requests,
            "zero_token_rate": self.zero_token_rate,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": self.cache_hit_rate,
            "tokens_per_capability": dict(
                self.tokens_per_capability
            ),
        }
