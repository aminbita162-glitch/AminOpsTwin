"""G4.6 — Experience promotion tests (P4, §32).

Zero unauthorized promotions; every active experience record links to
complete evaluation and owner approval. Rejection and rollback paths pass.
"""

from __future__ import annotations

import hashlib

import pytest
from aminopstwin.executor.experience import (
    ExperienceError,
    ExperienceStatus,
    ExperienceStore,
)


def _make_store() -> ExperienceStore:
    return ExperienceStore()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class TestExperienceLifecycle:
    """OBSERVED -> CANDIDATE -> EVALUATED -> OWNER_APPROVED -> ACTIVE."""

    def test_observe_creates_observed(self) -> None:
        store = _make_store()
        record = store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
        )
        assert record.status is ExperienceStatus.OBSERVED

    def test_full_lifecycle_to_active(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
            evidence_refs=["evidence-001"],
        )
        store.transition("exp-001", ExperienceStatus.CANDIDATE)
        store.transition("exp-001", ExperienceStatus.EVALUATED)
        store.transition(
            "exp-001",
            ExperienceStatus.OWNER_APPROVED,
            owner_approval="owner-2026-10-23",
        )
        store.transition(
            "exp-001",
            ExperienceStatus.ACTIVE,
            evaluation_evidence="eval-evidence-001",
        )
        assert store.is_active("exp-001")

    def test_invalid_transition_rejected(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
        )
        # Cannot jump from OBSERVED directly to ACTIVE
        with pytest.raises(ExperienceError):
            store.transition("exp-001", ExperienceStatus.ACTIVE)

    def test_owner_approved_requires_approval(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
        )
        store.transition("exp-001", ExperienceStatus.CANDIDATE)
        store.transition("exp-001", ExperienceStatus.EVALUATED)
        with pytest.raises(ExperienceError, match="owner_approval"):
            store.transition("exp-001", ExperienceStatus.OWNER_APPROVED)

    def test_active_requires_evaluation_evidence(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
        )
        store.transition("exp-001", ExperienceStatus.CANDIDATE)
        store.transition("exp-001", ExperienceStatus.EVALUATED)
        store.transition(
            "exp-001",
            ExperienceStatus.OWNER_APPROVED,
            owner_approval="owner",
        )
        # Cannot go ACTIVE without evaluation_evidence
        with pytest.raises(ExperienceError, match="evaluation_evidence"):
            store.transition("exp-001", ExperienceStatus.ACTIVE)

    def test_active_requires_owner_approved_first(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
        )
        store.transition("exp-001", ExperienceStatus.CANDIDATE)
        store.transition("exp-001", ExperienceStatus.EVALUATED)
        # Skip OWNER_APPROVED -> cannot go ACTIVE
        with pytest.raises(ExperienceError):
            store.transition(
                "exp-001",
                ExperienceStatus.ACTIVE,
                evaluation_evidence="ev",
            )


class TestUnauthorizedPromotion:
    """G4.6: zero unauthorized promotions."""

    def test_unauthorized_active_not_in_active_set(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
        )
        # Only OBSERVED, not ACTIVE
        assert not store.is_active("exp-001")
        assert len(store.active_records()) == 0

    def test_active_records_have_owner_approval(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
            evidence_refs=["ev-1"],
        )
        store.transition("exp-001", ExperienceStatus.CANDIDATE)
        store.transition("exp-001", ExperienceStatus.EVALUATED)
        store.transition(
            "exp-001",
            ExperienceStatus.OWNER_APPROVED,
            owner_approval="owner",
        )
        store.transition(
            "exp-001",
            ExperienceStatus.ACTIVE,
            evaluation_evidence="ev-1",
        )
        for record in store.active_records():
            assert record.owner_approval is not None
            assert record.evaluation_evidence is not None


class TestRetirementAndQuarantine:
    """Rejection and rollback paths pass their fixtures."""

    def test_retire_from_active(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
            evidence_refs=["ev-1"],
        )
        store.transition("exp-001", ExperienceStatus.CANDIDATE)
        store.transition("exp-001", ExperienceStatus.EVALUATED)
        store.transition(
            "exp-001",
            ExperienceStatus.OWNER_APPROVED,
            owner_approval="owner",
        )
        store.transition(
            "exp-001",
            ExperienceStatus.ACTIVE,
            evaluation_evidence="ev-1",
        )
        store.transition("exp-001", ExperienceStatus.RETIRED)
        assert not store.is_active("exp-001")

    def test_quarantine_from_active(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
            evidence_refs=["ev-1"],
        )
        store.transition("exp-001", ExperienceStatus.CANDIDATE)
        store.transition("exp-001", ExperienceStatus.EVALUATED)
        store.transition(
            "exp-001",
            ExperienceStatus.OWNER_APPROVED,
            owner_approval="owner",
        )
        store.transition(
            "exp-001",
            ExperienceStatus.ACTIVE,
            evaluation_evidence="ev-1",
        )
        store.transition("exp-001", ExperienceStatus.QUARANTINED)
        assert not store.is_active("exp-001")

    def test_rollback_target_returns_supersedes(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
            evidence_refs=["ev-1"],
        )
        store.transition("exp-001", ExperienceStatus.CANDIDATE)
        store.transition("exp-001", ExperienceStatus.EVALUATED)
        store.transition(
            "exp-001",
            ExperienceStatus.OWNER_APPROVED,
            owner_approval="owner",
        )
        store.transition(
            "exp-001",
            ExperienceStatus.ACTIVE,
            evaluation_evidence="ev-1",
        )
        # No supersedes set -> rollback target is None
        assert store.rollback_target("exp-001") is None

    def test_duplicate_observe_rejected(self) -> None:
        store = _make_store()
        store.observe(
            experience_id="exp-001",
            task_category="capacity_planning",
            input_hash=_hash("input"),
            policy_epoch=0,
            selected_method="template_A",
            test_outcome="PASS",
        )
        with pytest.raises(ExperienceError):
            store.observe(
                experience_id="exp-001",
                task_category="capacity_planning",
                input_hash=_hash("input"),
                policy_epoch=0,
                selected_method="template_A",
                test_outcome="PASS",
            )
