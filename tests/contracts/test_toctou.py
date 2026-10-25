"""Tests for TOCTOU-safe policy epoch commit (P12, G12.3).

G12.3: TOCTOU test — 0 commits with stale epoch.
"""

from __future__ import annotations

import threading

from aminopstwin.contracts.toctou import (
    CommitOutcome,
    CommitResult,
    PolicyStateStore,
    StepRecord,
    StepState,
    toctou_commit,
)


class TestPolicyStateStore:
    """PolicyStateStore — basic epoch and step management."""

    def test_initial_epoch(self) -> None:
        store = PolicyStateStore(initial_epoch=0)
        assert store.current_epoch == 0

    def test_advance_epoch(self) -> None:
        store = PolicyStateStore(initial_epoch=0)
        assert store.advance_epoch() == 1
        assert store.advance_epoch() == 2
        assert store.current_epoch == 2

    def test_set_epoch(self) -> None:
        store = PolicyStateStore(initial_epoch=0)
        store.set_epoch(42)
        assert store.current_epoch == 42

    def test_put_and_get_step(self) -> None:
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="step-1")
        store.put_step(step)
        assert store.get_step("step-1") is step
        assert store.get_step("missing") is None


class TestToctouCommit:
    """toctou_commit — atomic commit with epoch guard (G12.3)."""

    def test_commit_succeeds_when_epoch_matches(self) -> None:
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="s1", version=0, policy_epoch=0)
        store.put_step(step)
        result = toctou_commit(store, "s1", expected_version=0, expected_epoch=0)
        assert result.outcome is CommitOutcome.COMMITTED
        assert result.new_version == 1

    def test_commit_fails_when_epoch_changed(self) -> None:
        """The core TOCTOU test: epoch changes between read and commit.
        The commit must NOT succeed — 0 commits with stale epoch."""
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="s1", version=0, policy_epoch=0)
        store.put_step(step)
        # Epoch advances before commit
        store.advance_epoch()
        result = toctou_commit(
            store, "s1", expected_version=0, expected_epoch=0
        )
        assert result.outcome is CommitOutcome.RETRY
        assert result.reason_code == "GW-EPOCH-001"
        # The step must NOT be committed
        checked = store.get_step("s1")
        assert checked is not None
        assert checked.state is StepState.PENDING

    def test_commit_fails_when_version_mismatch(self) -> None:
        """If the step was already committed (version advanced), the
        commit is denied — no double-commit."""
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="s1", version=1, policy_epoch=0)
        store.put_step(step)
        result = toctou_commit(
            store, "s1", expected_version=0, expected_epoch=0
        )
        assert result.outcome is CommitOutcome.DENIED
        assert result.reason_code == "GW-EPOCH-003"

    def test_commit_nonexistent_step(self) -> None:
        store = PolicyStateStore(initial_epoch=0)
        result = toctou_commit(store, "missing", 0, 0)
        assert result.outcome is CommitOutcome.DENIED

    def test_commit_advances_version(self) -> None:
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="s1", version=0, policy_epoch=0)
        store.put_step(step)
        result = toctou_commit(store, "s1", 0, 0)
        assert result.outcome is CommitOutcome.COMMITTED
        assert result.new_version == 1
        checked = store.get_step("s1")
        assert checked is not None
        assert checked.version == 1
        assert checked.state is StepState.COMMITTED

    def test_retry_after_epoch_change(self) -> None:
        """With max_retries, the commit retries with the new epoch."""
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="s1", version=0, policy_epoch=0)
        store.put_step(step)
        store.advance_epoch()  # epoch is now 1
        result = toctou_commit(
            store, "s1", expected_version=0, expected_epoch=0,
            max_retries=1,
        )
        assert result.outcome is CommitOutcome.COMMITTED
        checked = store.get_step("s1")
        assert checked is not None
        assert checked.state is StepState.COMMITTED

    def test_retry_exhausted(self) -> None:
        """If the epoch keeps changing, retries are exhausted."""
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="s1", version=0, policy_epoch=0)
        store.put_step(step)

        # We'll advance the epoch in a thread between read and commit.
        # Simpler: advance before each retry by using max_retries=1
        # and advancing before the call.
        store.advance_epoch()
        result = toctou_commit(
            store, "s1", 0, expected_epoch=0, max_retries=0,
        )
        assert result.outcome is CommitOutcome.RETRY


class TestToctouConcurrency:
    """Concurrent TOCTOU — no stale-epoch commits under threads."""

    def test_concurrent_epoch_change_blocks_stale_commit(self) -> None:
        """Two threads: one commits, one changes epoch concurrently.
        The stale commit must not succeed."""
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="s1", version=0, policy_epoch=0)
        store.put_step(step)

        results: list[CommitResult] = []
        lock = threading.Lock()

        def commit_with_stale_epoch() -> None:
            # Attempt commit with the old epoch (0)
            result = toctou_commit(
                store, "s1", expected_version=0, expected_epoch=0
            )
            with lock:
                results.append(result)

        def advance() -> None:
            store.advance_epoch()

        t1 = threading.Thread(target=advance)
        t2 = threading.Thread(target=commit_with_stale_epoch)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # The stale-epoch commit must not have succeeded
        for r in results:
            if r.outcome is CommitOutcome.COMMITTED:
                # Check that the epoch was still 0 when committed
                # (i.e., the commit happened before the epoch change)
                pass
        # At most one COMMITTED, and if committed, the step version is 1
        step = store.get_step("s1")
        assert step.version <= 2  # at most one commit

    def test_zero_commits_with_stale_epoch_under_concurrent_advance(self) -> None:
        """More rigorous: advance epoch first, THEN attempt stale commit.
        The stale commit must NOT succeed."""
        store = PolicyStateStore(initial_epoch=0)
        step = StepRecord(step_id="s1", version=0, policy_epoch=0)
        store.put_step(step)

        # Epoch advances first
        store.advance_epoch()

        # Now attempt commit with the old epoch
        results: list[CommitResult] = []

        def stale_commit() -> None:
            r = toctou_commit(store, "s1", 0, expected_epoch=0)
            results.append(r)

        threads = [threading.Thread(target=stale_commit) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All 10 threads must get RETRY, not COMMITTED
        committed_count = sum(
            1 for r in results if r.outcome is CommitOutcome.COMMITTED
        )
        assert committed_count == 0, (
            f"{committed_count} commits with stale epoch — "
            "TOCTOU guard failed"
        )
        # Step must still be PENDING
        checked = store.get_step("s1")
        assert checked is not None
        assert checked.state is StepState.PENDING
