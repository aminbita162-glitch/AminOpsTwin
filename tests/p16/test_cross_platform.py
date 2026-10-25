"""G16.2 — Cross-platform oracle green (P16).

The CI matrix (ubuntu-latest + macos-14) runs the fixed workload and
compares state hashes.  This test verifies the oracle workload is
reproducible on the local platform and records the platform hash for
CI comparison.  On mismatch, a structural diff is emitted.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass

import pytest
from aminopstwin.twin.cross_process_rng import cross_process_stream_check
from aminopstwin.twin.entities import Queue, Resource, Site
from aminopstwin.twin.integer_clock import (
    MilliMinuteClock,
    PrngRegistry,
)
from aminopstwin.twin.temporal import TemporalState


@dataclass(frozen=True)
class PlatformHashRecord:
    """A recorded state hash for a specific platform/Python version."""

    architecture: str
    python_version: str
    state_hash: str


def _platform_key() -> str:
    """Return a platform key string."""
    machine = platform.machine()
    return f"{sys.platform}-{machine}"


def _run_oracle_workload() -> str:
    """Run the fixed oracle workload and return the state hash.

    This is the same workload as the P12 cross-platform oracle
    (G12.5), extended for P16 with the working calendar and named
    PRNG streams.
    """
    state = TemporalState(seed=42)
    clock = MilliMinuteClock(start_mmin=0, step_mmin=100)
    prng = PrngRegistry(master_seed=42)

    # Set up 3 sites, each with 2 resources and 1 queue
    for s in range(3):
        site_id = f"site-{s:04d}"
        state.add_site(
            Site(site_id=site_id, name=f"Site {s}", capacity=20)
        )
        for r in range(2):
            rid = f"res-{site_id}-{r:04d}"
            state.add_resource(
                Resource(
                    resource_id=rid,
                    site_id=site_id,
                    name=f"Resource {r} at Site {s}",
                    capacity=10,
                    available=10,
                )
            )
        qid = f"queue-{site_id}-0000"
        state.add_queue(
            Queue(
                queue_id=qid,
                site_id=site_id,
                name=f"Queue 0 at Site {s}",
                current_length=0,
                total_arrivals=0,
                total_completions=0,
                capacity=10,
            )
        )

    # Run 50 ticks with deterministic arrivals
    for t in range(50):
        mmin = clock.tick()
        stream = prng.get_stream(f"tick-{t:04d}")
        n_arrivals = stream.randint(0, 5)
        for _ in range(n_arrivals):
            site_idx = stream.randint(0, 2)
            site_id = f"site-{site_idx:04d}"
            qid = f"queue-{site_id}-0000"
            state.add_arrival(
                site_id=site_id,
                queue_id=qid,
                arrival_time=mmin,
                service_time=stream.randint(1, 10),
            )
        state.advance()

    return state.final_hash()


def _structural_diff(hash_a: str, hash_b: str) -> str:
    """Emit a structural diff for hash mismatch."""
    return (
        f"  Platform A hash: {hash_a}\n"
        f"  Platform B hash: {hash_b}\n"
        f"  Differ at position: "
        f"{next((i for i, (a, b) in enumerate(zip(hash_a, hash_b)) if a != b), 'N/A')}\n"
    )


class TestCrossPlatformOracle:
    """Cross-platform oracle — reproducible state hash."""

    def test_oracle_hash_reproducible(self) -> None:
        """The oracle workload hash is reproducible on this platform."""
        h1 = _run_oracle_workload()
        h2 = _run_oracle_workload()
        assert h1 == h2, _structural_diff(h1, h2)

    def test_platform_recorded(self) -> None:
        """The platform is detected and the hash recorded."""
        record = PlatformHashRecord(
            architecture=_platform_key(),
            python_version=f"{sys.version_info[:2][0]}.{sys.version_info[:2][1]}",
            state_hash=_run_oracle_workload(),
        )
        assert record.architecture
        assert len(record.state_hash) == 64
        # Print for CI log capture
        print(f"\n  Platform: {record.architecture}")
        print(f"  Python: {record.python_version}")
        print(f"  Oracle hash: {record.state_hash}")

    def test_cross_process_rng_identical(self) -> None:
        """Cross-process RNG streams are identical."""
        result = cross_process_stream_check(
            seed=42, stream_id="oracle", count=50
        )
        assert result.identical, (
            f"Cross-process RNG mismatch: "
            f"seq_a={result.sequence_a[:5]}..., "
            f"seq_b={result.sequence_b[:5]}..."
        )

    def test_ci_matrix_runs_both_platforms(self) -> None:
        """Document that CI runs on both ubuntu-latest and macos-14.

        This test verifies that the CI workflow file declares both
        platforms.  The actual cross-platform comparison happens in CI.
        """
        from pathlib import Path

        ci_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"
        if not ci_path.exists():
            pytest.skip("ci.yml not found")
        content = ci_path.read_text()
        # The CI workflow should have both ubuntu-latest and macos-14
        assert "ubuntu-latest" in content
        assert "macos-14" in content
