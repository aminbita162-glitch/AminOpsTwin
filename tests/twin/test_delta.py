"""Delta compression tests (G3.4).

Verifies that reconstructed state hash equals the original in
100% of tested snapshots; size reduction is reported.
"""

from __future__ import annotations

from src.twin.delta import DeltaCompressor
from src.twin.entities import (
    Queue,
    Site,
)
from src.twin.temporal import TemporalState, snapshot_hash


class TestDeltaCompression:
    """Delta compression round-trip tests (G3.4)."""

    def _build_state(self, seed: int = 42) -> TemporalState:
        state = TemporalState(seed=seed)
        state.add_site(
            Site(site_id="s1", name="Site 1", capacity=10)
        )
        state.add_queue(
            Queue(
                queue_id="q1",
                site_id="s1",
                name="Queue 1",
                current_length=0,
                total_arrivals=0,
                total_completions=0,
                capacity=100,
            )
        )
        return state

    def test_delta_round_trip_identical_hash(self) -> None:
        """Delta's target_hash matches the actual snapshot hash."""
        state = self._build_state()
        state.advance()
        base = state.get_snapshot()

        state.add_arrival("s1", "q1", 0, 5)
        state.advance()
        target = state.get_snapshot()

        assert DeltaCompressor.verify_round_trip(base, target)

    def test_delta_round_trip_multiple_snapshots(self) -> None:
        """100% of tested snapshots reconstruct correctly."""
        state = self._build_state()
        snapshots: list = []

        for i in range(50):
            state.add_arrival("s1", "q1", i, 5)
            state.advance()
            snapshots.append(state.get_snapshot())

        for j in range(1, len(snapshots)):
            base = snapshots[j - 1]
            target = snapshots[j]
            assert DeltaCompressor.verify_round_trip(base, target)

    def test_delta_size_reported(self) -> None:
        """Delta size_bytes is reported and is positive."""
        state = self._build_state()
        state.advance()
        base = state.get_snapshot()

        state.add_arrival("s1", "q1", 0, 5)
        state.advance()
        target = state.get_snapshot()

        delta = DeltaCompressor.compute_delta(base, target)
        assert delta.size_bytes > 0

    def test_delta_compression_ratio(self) -> None:
        """Compression ratio is computed and is positive."""
        state = self._build_state()
        for i in range(20):
            state.add_arrival("s1", "q1", i, 5)
            state.advance()
        base = state.get_snapshot()

        for i in range(20, 40):
            state.add_arrival("s1", "q1", i, 5)
            state.advance()
        target = state.get_snapshot()

        ratio = DeltaCompressor.compression_ratio(base, target)
        assert ratio > 0.0

    def test_delta_empty_state(self) -> None:
        """Empty snapshots produce a valid delta."""
        state = TemporalState(seed=42)
        state.advance()
        base = state.get_snapshot()

        state.advance()
        target = state.get_snapshot()

        assert DeltaCompressor.verify_round_trip(base, target)

    def test_delta_with_completions(self) -> None:
        """Delta works with service completions."""
        state = self._build_state()
        state.advance()
        base = state.get_snapshot()

        state.add_arrival("s1", "q1", 0, 5)
        state.add_completion("s1", "q1", "arr-1", 0, 5)
        state.advance()
        target = state.get_snapshot()

        assert DeltaCompressor.verify_round_trip(base, target)

    def test_delta_reconstruct_hash(self) -> None:
        """reconstruct_hash returns the target_hash."""
        state = self._build_state()
        state.advance()
        base = state.get_snapshot()

        state.add_arrival("s1", "q1", 0, 5)
        state.advance()
        target = state.get_snapshot()

        delta = DeltaCompressor.compute_delta(base, target)
        assert DeltaCompressor.reconstruct_hash(delta) == (
            delta.target_hash
        )
        assert delta.target_hash == snapshot_hash(target)
