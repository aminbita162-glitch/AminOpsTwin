"""Tests for crash-safe IdFactory implementations (P12, G12.2).

G12.2: crash-recovery test produces no duplicate or orphan IDs.
"""

from __future__ import annotations

import uuid

import pytest
from aminopstwin.contracts.idfactory import (
    DeterministicIdFactory,
    EntropyIdFactory,
    IdRegistry,
    step_id,
)


class TestDeterministicIdFactory:
    """DeterministicIdFactory — HMAC-SHA256-based deterministic UUIDs."""

    def test_same_seed_same_sequence(self) -> None:
        f1 = DeterministicIdFactory(seed=b"test-seed", domain="wf")
        f2 = DeterministicIdFactory(seed=b"test-seed", domain="wf")
        ids1 = [str(f1.new_id()) for _ in range(10)]
        ids2 = [str(f2.new_id()) for _ in range(10)]
        assert ids1 == ids2

    def test_different_seed_different_sequence(self) -> None:
        f1 = DeterministicIdFactory(seed=b"seed-a", domain="wf")
        f2 = DeterministicIdFactory(seed=b"seed-b", domain="wf")
        assert str(f1.new_id()) != str(f2.new_id())

    def test_different_domain_different_sequence(self) -> None:
        f1 = DeterministicIdFactory(seed=b"test-seed", domain="wf")
        f2 = DeterministicIdFactory(seed=b"test-seed", domain="other")
        assert str(f1.new_id()) != str(f2.new_id())

    def test_monotonic_counter(self) -> None:
        f = DeterministicIdFactory(seed=b"test-seed", domain="wf")
        assert f.counter == 0
        f.new_id()
        assert f.counter == 1
        f.new_id()
        assert f.counter == 2

    def test_id_at_does_not_advance_counter(self) -> None:
        f = DeterministicIdFactory(seed=b"test-seed", domain="wf")
        _ = f.id_at(5)
        assert f.counter == 0

    def test_id_at_matches_new_id(self) -> None:
        f = DeterministicIdFactory(seed=b"test-seed", domain="wf")
        expected = f.id_at(0)
        actual = f.new_id()
        assert expected == actual

    def test_uuid_version_4(self) -> None:
        f = DeterministicIdFactory(seed=b"test-seed", domain="wf")
        u = f.new_id()
        assert u.version == 4

    def test_reset(self) -> None:
        f = DeterministicIdFactory(seed=b"test-seed", domain="wf")
        first = f.new_id()
        f.reset()
        first_again = f.new_id()
        assert first == first_again

    def test_string_seed(self) -> None:
        f1 = DeterministicIdFactory(seed="string-seed", domain="wf")
        f2 = DeterministicIdFactory(seed="string-seed", domain="wf")
        assert str(f1.new_id()) == str(f2.new_id())


class TestEntropyIdFactory:
    """EntropyIdFactory — secrets.token_bytes-backed."""

    def test_unique_ids(self) -> None:
        f = EntropyIdFactory()
        ids = {str(f.new_id()) for _ in range(100)}
        assert len(ids) == 100

    def test_uuid_version_4(self) -> None:
        f = EntropyIdFactory()
        u = f.new_id()
        assert u.version == 4

    def test_counter_increments(self) -> None:
        f = EntropyIdFactory()
        assert f.counter == 0
        f.new_id()
        assert f.counter == 1


class TestStepId:
    """step_id — crash-safe deterministic step identifiers."""

    def test_deterministic(self) -> None:
        wf = uuid.uuid4()
        s1 = step_id(wf, 0, 0)
        s2 = step_id(wf, 0, 0)
        assert s1 == s2

    def test_different_step_no(self) -> None:
        wf = uuid.uuid4()
        assert step_id(wf, 0, 0) != step_id(wf, 1, 0)

    def test_different_attempt(self) -> None:
        wf = uuid.uuid4()
        assert step_id(wf, 0, 0) != step_id(wf, 0, 1)

    def test_different_workflow(self) -> None:
        assert step_id(uuid.uuid4(), 0, 0) != step_id(uuid.uuid4(), 0, 0)

    def test_hex_string(self) -> None:
        wf = uuid.uuid4()
        sid = step_id(wf, 0, 0)
        assert len(sid) == 16
        assert all(c in "0123456789abcdef" for c in sid)


class TestIdRegistryCrashRecovery:
    """IdRegistry — no duplicates or orphans after simulated crash (G12.2)."""

    def test_no_duplicates_after_replay(self) -> None:
        """Simulate a crash: register steps, then replay and verify
        no duplicates are produced."""
        wf = uuid.uuid4()
        registry = IdRegistry()
        registry.register_workflow(wf)

        # Issue some steps
        sids: list[str] = []
        for step_no in range(5):
            sid = registry.register_step(wf, step_no, attempt=0)
            sids.append(sid)

        # Simulate crash + recovery: create a new registry and replay
        registry2 = IdRegistry()
        registry2.register_workflow(wf)
        replayed: list[str] = []
        for step_no in range(5):
            sid = registry2.register_step(wf, step_no, attempt=0)
            replayed.append(sid)

        assert sids == replayed
        assert len(set(replayed)) == len(replayed)

    def test_orphan_rejected(self) -> None:
        registry = IdRegistry()
        wf = uuid.uuid4()
        with pytest.raises(ValueError, match="orphan step"):
            registry.register_step(wf, 0, 0)

    def test_duplicate_step_rejected(self) -> None:
        registry = IdRegistry()
        wf = uuid.uuid4()
        registry.register_workflow(wf)
        registry.register_step(wf, 0, 0)
        with pytest.raises(ValueError, match="duplicate step_id"):
            registry.register_step(wf, 0, 0)

    def test_retry_with_new_attempt_not_duplicate(self) -> None:
        """A retried step gets a new attempt number — not a duplicate."""
        registry = IdRegistry()
        wf = uuid.uuid4()
        registry.register_workflow(wf)
        sid0 = registry.register_step(wf, 0, attempt=0)
        sid1 = registry.register_step(wf, 0, attempt=1)
        assert sid0 != sid1
        assert registry.step_count == 2

    def test_multiple_workflows(self) -> None:
        registry = IdRegistry()
        wf1 = uuid.uuid4()
        wf2 = uuid.uuid4()
        registry.register_workflow(wf1)
        registry.register_workflow(wf2)
        s1 = registry.register_step(wf1, 0, 0)
        s2 = registry.register_step(wf2, 0, 0)
        assert s1 != s2
        assert registry.workflow_count == 2
        assert registry.step_count == 2

    def test_crash_recovery_no_orphans(self) -> None:
        """Full crash-recovery scenario: commit 3 steps, crash,
        restart, replay all 3 — no orphans, no duplicates."""
        wf = uuid.uuid4()

        # Original run
        reg1 = IdRegistry()
        reg1.register_workflow(wf)
        committed = [reg1.register_step(wf, i, 0) for i in range(3)]

        # Crash: reg1 is lost. Recovery:
        reg2 = IdRegistry()
        reg2.register_workflow(wf)
        for i, sid in enumerate(committed):
            # Check the replayed step_id matches the original
            assert reg2.has_step(wf, i, 0) is False
            new_sid = reg2.register_step(wf, i, 0)
            assert new_sid == sid

        # No orphans: all steps belong to a registered workflow
        assert reg2.step_count == 3
        assert reg2.workflow_count == 1
        assert reg2.issued_step_ids() == sorted(committed)

    def test_duplicate_workflow_rejected(self) -> None:
        registry = IdRegistry()
        wf = uuid.uuid4()
        registry.register_workflow(wf)
        with pytest.raises(ValueError, match="duplicate workflow_id"):
            registry.register_workflow(wf)
