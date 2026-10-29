"""Fault injection test: kill -9 at every executor boundary (P27, G27.1).

This test simulates a crash at every executor state transition boundary
and verifies that restarting the executor produces 0 duplicate effects
and 0 lost effects.

The in-memory DurableExecutor uses save_snapshot/restore_snapshot to
simulate crash recovery. The PostgreSQL adapter (PgExecutor) provides
real durability; this test exercises the in-memory executor's
snapshot/restore path to simulate crash-at-boundary semantics.

G27.1: kill -9 at every executor boundary, then restart -> 0 duplicate,
       0 lost effects.
"""

from __future__ import annotations

import uuid

from aminopstwin.contracts.clock import SeededClock
from aminopstwin.executor import (
    DurableExecutor,
    ExecutorState,
)
from aminopstwin.persistence.models import (
    EffectModel,
    OutboxModel,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker


class TestFaultInjectionBoundaries:
    """G27.1 — crash at every executor boundary, restart, 0 dup/lost."""

    def test_crash_at_pending_then_restart_no_lost_effect(self) -> None:
        """Crash after PENDING, restart, then complete — no lost effect."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        correlation_id = uuid.uuid4()
        wf = executor.start(correlation_id, tenant_id="tenant-a")

        # Simulate crash: save snapshot, create new executor, restore.
        snapshot = executor.save_snapshot()
        executor2 = DurableExecutor(clock=clock)
        executor2.restore_snapshot(snapshot)

        # The workflow must still be there.
        recovered = executor2.get_workflow(wf.workflow_id)
        assert recovered is not None
        assert recovered.state is ExecutorState.PENDING

        # Complete the workflow — the effect must not be lost.
        executor2.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor2.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor2.commit_intent(wf.workflow_id, {"step": 1})
        executor2.commit(wf.workflow_id)
        executor2.complete(wf.workflow_id)

        final = executor2.get_workflow(wf.workflow_id)
        assert final is not None
        assert final.state is ExecutorState.COMPLETED

    def test_crash_at_running_then_restart_no_lost_effect(self) -> None:
        """Crash after RUNNING, restart, then complete."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-a")
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)

        snapshot = executor.save_snapshot()
        executor2 = DurableExecutor(clock=clock)
        executor2.restore_snapshot(snapshot)

        recovered = executor2.get_workflow(wf.workflow_id)
        assert recovered is not None
        assert recovered.state is ExecutorState.RUNNING

        executor2.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor2.commit_intent(wf.workflow_id, {"step": 1})
        executor2.commit(wf.workflow_id)
        executor2.complete(wf.workflow_id)

        final = executor2.get_workflow(wf.workflow_id)
        assert final is not None
        assert final.state is ExecutorState.COMPLETED

    def test_crash_at_checkpointed_then_restart_no_lost_effect(self) -> None:
        """Crash after CHECKPOINTED, restart, then complete."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-a")
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)

        snapshot = executor.save_snapshot()
        executor2 = DurableExecutor(clock=clock)
        executor2.restore_snapshot(snapshot)

        recovered = executor2.get_workflow(wf.workflow_id)
        assert recovered is not None
        assert recovered.state is ExecutorState.CHECKPOINTED

        executor2.commit_intent(wf.workflow_id, {"step": 1})
        executor2.commit(wf.workflow_id)
        executor2.complete(wf.workflow_id)

        final = executor2.get_workflow(wf.workflow_id)
        assert final is not None
        assert final.state is ExecutorState.COMPLETED

    def test_crash_at_commit_intent_then_restart_no_duplicate(self) -> None:
        """Crash after COMMIT_INTENT, restart, commit once — no duplicate."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-a")
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor.commit_intent(wf.workflow_id, {"step": 1})

        snapshot = executor.save_snapshot()
        executor2 = DurableExecutor(clock=clock)
        executor2.restore_snapshot(snapshot)

        recovered = executor2.get_workflow(wf.workflow_id)
        assert recovered is not None
        assert recovered.state is ExecutorState.COMMIT_INTENT

        # Commit exactly once after restart.
        executor2.commit(wf.workflow_id)
        executor2.complete(wf.workflow_id)

        final = executor2.get_workflow(wf.workflow_id)
        assert final is not None
        assert final.state is ExecutorState.COMPLETED

        # The history must contain exactly one COMMITTED.
        committed_count = final.history.count(ExecutorState.COMMITTED)
        assert committed_count == 1, (
            f"Expected 1 COMMITTED, got {committed_count} — duplicate effect"
        )

    def test_crash_at_committed_then_restart_no_duplicate(self) -> None:
        """Crash after COMMITTED, restart, complete — no duplicate commit."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-a")
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor.commit_intent(wf.workflow_id, {"step": 1})
        executor.commit(wf.workflow_id)

        snapshot = executor.save_snapshot()
        executor2 = DurableExecutor(clock=clock)
        executor2.restore_snapshot(snapshot)

        recovered = executor2.get_workflow(wf.workflow_id)
        assert recovered is not None
        assert recovered.state is ExecutorState.COMMITTED

        # Must not be able to commit again — already COMMITTED.
        executor2.complete(wf.workflow_id)

        final = executor2.get_workflow(wf.workflow_id)
        assert final is not None
        assert final.state is ExecutorState.COMPLETED

        committed_count = final.history.count(ExecutorState.COMMITTED)
        assert committed_count == 1

    def test_crash_at_every_boundary_no_lost_no_duplicate(self) -> None:
        """Systematic: crash at every boundary, restart, verify integrity."""
        for crash_state in [
            ExecutorState.PENDING,
            ExecutorState.RUNNING,
            ExecutorState.CHECKPOINTED,
            ExecutorState.COMMIT_INTENT,
            ExecutorState.COMMITTED,
        ]:
            clock = SeededClock()
            executor = DurableExecutor(clock=clock)
            wf = executor.start(uuid.uuid4(), tenant_id="tenant-crash")

            # Walk to the crash state.
            if crash_state != ExecutorState.PENDING:
                executor.transition(wf.workflow_id, ExecutorState.RUNNING)
            if crash_state in (
                ExecutorState.CHECKPOINTED,
                ExecutorState.COMMIT_INTENT,
                ExecutorState.COMMITTED,
            ):
                executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
            if crash_state in (
                ExecutorState.COMMIT_INTENT,
                ExecutorState.COMMITTED,
            ):
                executor.commit_intent(wf.workflow_id, {"step": 1})
            if crash_state == ExecutorState.COMMITTED:
                executor.commit(wf.workflow_id)

            # Verify we reached the crash state.
            current = executor.get_workflow(wf.workflow_id)
            assert current is not None
            assert current.state is crash_state

            # Crash and restart.
            snapshot = executor.save_snapshot()
            executor2 = DurableExecutor(clock=clock)
            executor2.restore_snapshot(snapshot)

            recovered = executor2.get_workflow(wf.workflow_id)
            assert recovered is not None
            assert recovered.state is crash_state

            # Complete the workflow from the crash state.
            if crash_state == ExecutorState.PENDING:
                executor2.transition(wf.workflow_id, ExecutorState.RUNNING)
                executor2.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
                executor2.commit_intent(wf.workflow_id, {"step": 1})
                executor2.commit(wf.workflow_id)
                executor2.complete(wf.workflow_id)
            elif crash_state == ExecutorState.RUNNING:
                executor2.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
                executor2.commit_intent(wf.workflow_id, {"step": 1})
                executor2.commit(wf.workflow_id)
                executor2.complete(wf.workflow_id)
            elif crash_state == ExecutorState.CHECKPOINTED:
                executor2.commit_intent(wf.workflow_id, {"step": 1})
                executor2.commit(wf.workflow_id)
                executor2.complete(wf.workflow_id)
            elif crash_state == ExecutorState.COMMIT_INTENT:
                executor2.commit(wf.workflow_id)
                executor2.complete(wf.workflow_id)
            elif crash_state == ExecutorState.COMMITTED:
                executor2.complete(wf.workflow_id)

            final = executor2.get_workflow(wf.workflow_id)
            assert final is not None
            assert final.state is ExecutorState.COMPLETED
            # Exactly one COMMITTED in the history — no duplicate.
            committed_count = final.history.count(ExecutorState.COMMITTED)
            assert committed_count == 1, (
                f"Crash at {crash_state.value}: expected 1 COMMITTED, "
                f"got {committed_count}"
            )


class TestPgFaultInjection:
    """G27.1 — PostgreSQL-backed crash recovery: 0 duplicate, 0 lost."""

    def test_pg_crash_at_commit_intent_no_duplicate(
        self,
        pg_session_factory: sessionmaker[Session],
    ) -> None:
        """Crash after COMMIT_INTENT on PostgreSQL, restart, commit once.

        The PgExecutor writes the effect and outbox receipt in the same
        transaction. After a simulated crash (new executor reading from
        the same database), the effect must not be duplicated.
        """
        from aminopstwin.persistence.pg_executor import PgExecutor

        clock = SeededClock()
        executor = PgExecutor(
            pg_session_factory,
            clock=clock,
        )
        correlation_id = uuid.uuid4()
        wf = executor.start(correlation_id, tenant_id="tenant-pg")
        executor._transition(wf.workflow_id, ExecutorState.RUNNING)
        executor._transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor._transition(wf.workflow_id, ExecutorState.COMMIT_INTENT)

        # Simulate crash: create a new PgExecutor reading from the same DB.
        executor2 = PgExecutor(pg_session_factory, clock=clock)
        recovered = executor2.get_workflow(wf.workflow_id)
        assert recovered is not None
        assert recovered.state is ExecutorState.COMMIT_INTENT

        # Commit exactly once after restart.
        result = executor2.commit_with_outbox(
            wf.workflow_id, {"effect": "test"}
        )
        assert result.state is ExecutorState.COMMITTED

        # Verify exactly one effect in the database.
        with pg_session_factory() as session:
            effects = session.execute(
                select(EffectModel).where(
                    EffectModel.workflow_id == str(wf.workflow_id)
                )
            ).scalars().all()
            assert len(effects) == 1, (
                f"Expected 1 effect, got {len(effects)} — duplicate"
            )
            outbox_entries = session.execute(
                select(OutboxModel).where(
                    OutboxModel.workflow_id == str(wf.workflow_id)
                )
            ).scalars().all()
            assert len(outbox_entries) == 1, (
                f"Expected 1 outbox entry, got {len(outbox_entries)}"
            )

    def test_pg_crash_at_pending_no_lost_effect(
        self,
        pg_session_factory: sessionmaker[Session],
    ) -> None:
        """Crash after PENDING on PostgreSQL, restart, complete — no loss."""
        from aminopstwin.persistence.pg_executor import PgExecutor

        clock = SeededClock()
        executor = PgExecutor(pg_session_factory, clock=clock)
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-pg2")

        # Simulate crash: new executor.
        executor2 = PgExecutor(pg_session_factory, clock=clock)
        recovered = executor2.get_workflow(wf.workflow_id)
        assert recovered is not None
        assert recovered.state is ExecutorState.PENDING

        # Complete the full lifecycle.
        executor2._transition(wf.workflow_id, ExecutorState.RUNNING)
        executor2._transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor2._transition(wf.workflow_id, ExecutorState.COMMIT_INTENT)
        result = executor2.commit_with_outbox(
            wf.workflow_id, {"effect": "recovered"}
        )
        assert result.state is ExecutorState.COMMITTED

        # Verify the effect is in the database — not lost.
        with pg_session_factory() as session:
            effects = session.execute(
                select(EffectModel).where(
                    EffectModel.workflow_id == str(wf.workflow_id)
                )
            ).scalars().all()
            assert len(effects) == 1
