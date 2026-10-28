"""Tests for P26 deliverable 3: Idempotency (ADR-004).

G26.3: 100 concurrent identical-key requests -> 1 effect.
G26.4: same key with a different payload -> GW-IDEMP-002.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from aminopstwin.contracts.idempotency import (
    IdempotencyError,
    IdempotencyStatus,
    InMemoryIdempotencyStore,
)


class TestIdempotencyStore:
    """Unit tests for InMemoryIdempotencyStore."""

    def test_get_or_start_new(self) -> None:
        store = InMemoryIdempotencyStore()
        result, started = store.get_or_start(
            "t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa"
        )
        assert started is True
        assert result.status is IdempotencyStatus.IN_PROGRESS
        assert result.fingerprint == "hash-aaa"

    def test_get_or_start_same_key_same_fingerprint(self) -> None:
        store = InMemoryIdempotencyStore()
        store.get_or_start("t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa")
        result, started = store.get_or_start(
            "t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa"
        )
        assert started is False
        assert result.status is IdempotencyStatus.IN_PROGRESS

    def test_get_or_start_same_key_different_fingerprint(self) -> None:
        store = InMemoryIdempotencyStore()
        store.get_or_start("t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa")
        with pytest.raises(IdempotencyError, match="GW-IDEMP-002"):
            store.get_or_start(
                "t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-bbb"
            )

    def test_commit(self) -> None:
        store = InMemoryIdempotencyStore()
        store.get_or_start("t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa")
        result = store.commit(
            "t1", "A1", "key-aaaaaaaaaaaaaaaa", "eff-001", {"ok": True}
        )
        assert result.status is IdempotencyStatus.COMMITTED
        assert result.effect_id == "eff-001"
        assert result.result == {"ok": True}

    def test_commit_after_commit_returns_existing(self) -> None:
        store = InMemoryIdempotencyStore()
        store.get_or_start("t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa")
        store.commit("t1", "A1", "key-aaaaaaaaaaaaaaaa", "eff-001", {"ok": True})
        result, started = store.get_or_start(
            "t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa"
        )
        assert started is False
        assert result.status is IdempotencyStatus.COMMITTED
        assert result.effect_id == "eff-001"

    def test_fail(self) -> None:
        store = InMemoryIdempotencyStore()
        store.get_or_start("t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa")
        result = store.fail("t1", "A1", "key-aaaaaaaaaaaaaaaa")
        assert result.status is IdempotencyStatus.FAILED

    def test_cross_tenant_isolation(self) -> None:
        store = InMemoryIdempotencyStore()
        store.get_or_start("t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa")
        result, started = store.get_or_start(
            "t2", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa"
        )
        assert started is True  # different tenant, different entry

    def test_cross_principal_isolation(self) -> None:
        store = InMemoryIdempotencyStore()
        store.get_or_start("t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa")
        result, started = store.get_or_start(
            "t1", "A2", "key-aaaaaaaaaaaaaaaa", "hash-aaa"
        )
        assert started is True  # different principal, different entry

    def test_get_nonexistent(self) -> None:
        store = InMemoryIdempotencyStore()
        assert store.get("t1", "A1", "nope") is None


class TestConcurrentIdempotency:
    """G26.3: 100 concurrent identical-key requests -> 1 effect."""

    def test_100_concurrent_same_key_one_effect(self) -> None:
        store = InMemoryIdempotencyStore()
        barrier = threading.Barrier(100)
        committed_count: list[int] = [0]
        lock = threading.Lock()

        def worker() -> None:
            barrier.wait()
            result, started = store.get_or_start(
                "t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa"
            )
            if started:
                with lock:
                    committed_count[0] += 1
                store.commit(
                    "t1", "A1", "key-aaaaaaaaaaaaaaaa", "eff-001", {"ok": True}
                )

        with ThreadPoolExecutor(max_workers=100) as pool:
            futures = [pool.submit(worker) for _ in range(100)]
            for f in futures:
                f.result()

        assert committed_count[0] == 1, (
            f"Expected 1 commit, got {committed_count[0]}"
        )
        result = store.get("t1", "A1", "key-aaaaaaaaaaaaaaaa")
        assert result is not None
        assert result.status is IdempotencyStatus.COMMITTED
        assert result.effect_id == "eff-001"

    def test_same_key_different_payload_raises_gw_idemp_002(self) -> None:
        """G26.4: same key with a different payload -> GW-IDEMP-002."""
        store = InMemoryIdempotencyStore()
        store.get_or_start("t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-aaa")
        with pytest.raises(IdempotencyError) as exc_info:
            store.get_or_start(
                "t1", "A1", "key-aaaaaaaaaaaaaaaa", "hash-bbb"
            )
        assert "GW-IDEMP-002" in str(exc_info.value)
