"""Cross-process deterministic RNG verification (P16, G16.2... item 7).

The deterministic RNG (``NamedPrngStream``, P12) uses
``H(seed || stream_id)`` to derive per-stream seeds.  This module
provides a cross-process verification: two independent Python processes
with the same seed and stream IDs must produce identical sequences.

The CI cross-platform oracle (G16.2) extends this to cross-platform:
the same sequence must be identical on x86_64 and ARM64.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from aminopstwin.twin.integer_clock import NamedPrngStream

__all__ = [
    "cross_process_stream_check",
    "CrossProcessResult",
]


class CrossProcessResult:
    """Result of a cross-process RNG stream check."""

    def __init__(
        self,
        stream_id: str,
        seed: int,
        sequence_a: list[int],
        sequence_b: list[int],
    ) -> None:
        self._stream_id: str = stream_id
        self._seed: int = seed
        self._sequence_a: list[int] = sequence_a
        self._sequence_b: list[int] = sequence_b
        self._identical: bool = sequence_a == sequence_b

    @property
    def stream_id(self) -> str:
        return self._stream_id

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def sequence_a(self) -> list[int]:
        return list(self._sequence_a)

    @property
    def sequence_b(self) -> list[int]:
        return list(self._sequence_b)

    @property
    def identical(self) -> bool:
        return self._identical

    def to_dict(self) -> dict[str, Any]:
        return {
            "stream_id": self._stream_id,
            "seed": self._seed,
            "identical": self._identical,
            "len_a": len(self._sequence_a),
            "len_b": len(self._sequence_b),
        }


def _generate_sequence(seed: int, stream_id: str, count: int) -> list[int]:
    """Generate a deterministic sequence in the current process."""
    stream = NamedPrngStream(seed, stream_id)
    return [stream.randint(0, 1_000_000) for _ in range(count)]


def cross_process_stream_check(
    seed: int = 42,
    stream_id: str = "test-stream",
    count: int = 100,
) -> CrossProcessResult:
    """Verify that two independent processes produce the same RNG sequence.

    Spawns a second Python process that generates ``count`` integers from
    the same (seed, stream_id).  Compares against the current process's
    sequence.
    """
    seq_a = _generate_sequence(seed, stream_id, count)

    # Spawn a subprocess to generate the same sequence
    code = (
        f"from aminopstwin.twin.integer_clock import NamedPrngStream\n"
        f"import json\n"
        f"stream = NamedPrngStream({seed}, '{stream_id}')\n"
        f"seq = [stream.randint(0, 1000000) for _ in range({count})]\n"
        f"print(json.dumps(seq))\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"subprocess failed: {result.stderr}"
        )

    import json
    seq_b: list[int] = json.loads(result.stdout.strip())

    return CrossProcessResult(stream_id, seed, seq_a, seq_b)
