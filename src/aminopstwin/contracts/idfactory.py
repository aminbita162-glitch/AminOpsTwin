"""IdFactory implementations for crash-safe deterministic IDs (P12, G12.2).

Two implementations:

DeterministicIdFactory
    HMAC-SHA256(seed, domain || counter) truncated and formatted as a
    UUID v4-layout.  Given the same seed, domain, and counter, the same
    UUID is always produced — no entropy, no time, no mutable state read.

EntropyIdFactory
    Backed by ``secrets.token_bytes`` — used only at the runtime edge
    where genuine entropy is required.  Never used in the deterministic
    core or in tests.

step_id
    ``step_id = H(workflow_id, step_no, attempt)`` — a deterministic
    identifier for a single step within a workflow, stable across
    crash-recovery retries.  The same (workflow_id, step_no, attempt)
    triple always yields the same step_id, so a crashed and restarted
    executor can detect whether a step was already committed without
    relying on mutable state.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid

__all__ = [
    "DeterministicIdFactory",
    "EntropyIdFactory",
    "step_id",
    "IdRegistry",
]


def _hmac_sha256(key: bytes, msg: bytes) -> bytes:
    """Return HMAC-SHA256(key, msg) — 32 raw bytes."""
    return hmac.new(key, msg, hashlib.sha256).digest()


def _bytes_to_uuid_v4(raw: bytes) -> uuid.UUID:
    """Format 16 bytes as a UUID v4-layout (RFC 4122).

    Version nibble at bits 76-79, variant bits at 62-63.
    """
    if len(raw) < 16:
        raw = raw + b"\x00" * (16 - len(raw))
    b = bytearray(raw[:16])
    b[6] = (b[6] & 0x0F) | 0x40  # version 4
    b[8] = (b[8] & 0x3F) | 0x80  # variant 10xx
    return uuid.UUID(bytes=bytes(b))


class DeterministicIdFactory:
    """HMAC-SHA256-seeded deterministic ID factory.

    ``id = UUID_v4_layout(HMAC-SHA256(seed, domain || counter))``

    The same (seed, domain, counter) always produces the same UUID.
    The counter is monotonic within a (seed, domain) pair; crash and
    recovery is modelled by re-seeding the factory — the same counter
    value will produce the same UUID, enabling idempotent retries.
    """

    def __init__(self, seed: bytes | str, domain: str = "default") -> None:
        if isinstance(seed, str):
            self._seed: bytes = seed.encode("utf-8")
        else:
            self._seed = seed
        self._domain: str = domain
        self._counter: int = 0

    @property
    def seed(self) -> bytes:
        return self._seed

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def counter(self) -> int:
        return self._counter

    def new_id(self) -> uuid.UUID:
        """Produce the next UUID deterministically from the counter."""
        raw = _hmac_sha256(
            self._seed,
            f"{self._domain}:{self._counter}".encode(),
        )
        self._counter += 1
        return _bytes_to_uuid_v4(raw)

    def id_at(self, counter: int) -> uuid.UUID:
        """Return the UUID that *would* be produced at ``counter``.

        Does not advance the internal counter.  This enables
        crash-safe replay: after a crash, the factory can check
        whether a given counter value was already committed by
        comparing the id_at(counter) against the persisted record.
        """
        raw = _hmac_sha256(
            self._seed,
            f"{self._domain}:{counter}".encode(),
        )
        return _bytes_to_uuid_v4(raw)

    def reset(self) -> None:
        """Reset the counter to 0 — used after crash-recovery replay."""
        self._counter = 0


class EntropyIdFactory:
    """Entropy-backed ID factory using ``secrets.token_bytes``.

    Used only at the runtime edge where genuine non-determinism is
    required.  Never used in the deterministic core.
    """

    def __init__(self, domain: str = "entropy") -> None:
        self._domain: str = domain
        self._counter: int = 0

    @property
    def domain(self) -> str:
        return self._domain

    @property
    def counter(self) -> int:
        return self._counter

    def new_id(self) -> uuid.UUID:
        raw = secrets.token_bytes(16)
        self._counter += 1
        return _bytes_to_uuid_v4(raw)


def step_id(
    workflow_id: uuid.UUID,
    step_no: int,
    attempt: int,
) -> str:
    """Compute a deterministic step identifier.

    ``step_id = SHA256(workflow_id || step_no || attempt)[:16]`` as
    a hex string.  The same (workflow_id, step_no, attempt) always
    produces the same string, enabling crash-safe retry detection:
    if the executor crashes after committing a step, the restarted
    executor computes the same step_id and can detect the prior commit.
    """
    h = hashlib.sha256()
    h.update(str(workflow_id).encode("utf-8"))
    h.update(b":")
    h.update(str(step_no).encode("utf-8"))
    h.update(b":")
    h.update(str(attempt).encode("utf-8"))
    return h.hexdigest()[:16]


class IdRegistry:
    """A registry of issued step_ids and workflow_ids.

    After a crash, the executor creates a fresh registry, replays the
    committed steps from the persisted log, and checks that no step_id
    is issued twice and no orphan step_ids remain (G12.2).
    """

    def __init__(self) -> None:
        self._issued: set[str] = set()
        self._workflow_ids: set[uuid.UUID] = set()

    def register_workflow(self, workflow_id: uuid.UUID) -> None:
        if workflow_id in self._workflow_ids:
            raise ValueError(
                f"duplicate workflow_id: {workflow_id}"
            )
        self._workflow_ids.add(workflow_id)

    def register_step(
        self,
        workflow_id: uuid.UUID,
        step_no: int,
        attempt: int,
    ) -> str:
        sid = step_id(workflow_id, step_no, attempt)
        if sid in self._issued:
            raise ValueError(
                f"duplicate step_id: {sid} "
                f"(workflow={workflow_id}, step={step_no}, "
                f"attempt={attempt})"
            )
        if workflow_id not in self._workflow_ids:
            raise ValueError(
                f"orphan step: workflow {workflow_id} not registered"
            )
        self._issued.add(sid)
        return sid

    def has_step(
        self,
        workflow_id: uuid.UUID,
        step_no: int,
        attempt: int,
    ) -> bool:
        return step_id(workflow_id, step_no, attempt) in self._issued

    @property
    def step_count(self) -> int:
        return len(self._issued)

    @property
    def workflow_count(self) -> int:
        return len(self._workflow_ids)

    def issued_step_ids(self) -> list[str]:
        return sorted(self._issued)
