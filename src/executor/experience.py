"""Controlled experience and learning (P4, §32, G4.6).

Capture sanitized structured experience from the first relevant execution.
Governed reuse and promotion of reusable operational patterns.

Lifecycle:
    OBSERVED -> CANDIDATE -> EVALUATED -> OWNER_APPROVED -> ACTIVE;
    ACTIVE -> RETIRED | QUARANTINED by authorized action.

Promotion requires complete evidence, no failed mandatory boundary/regression
checks, and owner approval. No online weight updates, self-modifying code,
autonomous policy relaxation, unapproved prompt changes, fine-tuning pipeline
or provider training permission is introduced.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ExperienceStatus",
    "ExperienceRecord",
    "ExperienceStore",
    "ExperienceError",
]


class ExperienceStatus(StrEnum):
    """Lifecycle states for an experience record (§32)."""

    OBSERVED = "OBSERVED"
    CANDIDATE = "CANDIDATE"
    EVALUATED = "EVALUATED"
    OWNER_APPROVED = "OWNER_APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    QUARANTINED = "QUARANTINED"


#: Valid lifecycle transitions.
_VALID_TRANSITIONS: dict[ExperienceStatus, frozenset[ExperienceStatus]] = {
    ExperienceStatus.OBSERVED: frozenset({ExperienceStatus.CANDIDATE}),
    ExperienceStatus.CANDIDATE: frozenset({ExperienceStatus.EVALUATED}),
    ExperienceStatus.EVALUATED: frozenset({ExperienceStatus.OWNER_APPROVED}),
    ExperienceStatus.OWNER_APPROVED: frozenset({ExperienceStatus.ACTIVE}),
    ExperienceStatus.ACTIVE: frozenset(
        {ExperienceStatus.RETIRED, ExperienceStatus.QUARANTINED}
    ),
    ExperienceStatus.RETIRED: frozenset(),
    ExperienceStatus.QUARANTINED: frozenset(),
}

#: Statuses that count as approved for promotion/activation.
_APPROVED_FOR_USE: frozenset[ExperienceStatus] = frozenset(
    {ExperienceStatus.OWNER_APPROVED, ExperienceStatus.ACTIVE}
)


class ExperienceError(Exception):
    """Raised when an experience lifecycle transition is invalid."""


class ExperienceRecord(BaseModel):
    """A single experience record (§32).

    model_config: frozen, strict, extra="forbid".

    Captures: task category, input/snapshot hashes, policy version, selected
    method, test outcome, explicit failure type, token/cost counters,
    evidence references. Does not store raw prompts, personal content,
    secrets or unvalidated model output.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    experience_id: str = Field(min_length=1, max_length=128)
    task_category: str = Field(min_length=1, max_length=64)
    input_hash: str = Field(min_length=64, max_length=64)
    snapshot_hash: str | None = None
    policy_epoch: int = Field(ge=0)
    selected_method: str = Field(min_length=1, max_length=128)
    test_outcome: str = Field(min_length=1, max_length=64)
    explicit_failure_type: str | None = None
    tokens_used: int = Field(default=0, ge=0)
    tokens_reserved: int = Field(default=0, ge=0)
    evidence_refs: list[str] = Field(default_factory=list)
    status: ExperienceStatus = ExperienceStatus.OBSERVED
    evaluation_evidence: str | None = None
    owner_approval: str | None = None
    supersedes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ExperienceStore:
    """Governed experience store with promotion controls (§32, G4.6).

    Zero unauthorized promotions: every active experience record links to
    complete evaluation and owner approval. Rejection and rollback paths
    pass their fixtures.
    """

    def __init__(self) -> None:
        self._records: dict[str, ExperienceRecord] = {}
        self._active: set[str] = set()

    def observe(
        self,
        experience_id: str,
        task_category: str,
        input_hash: str,
        policy_epoch: int,
        selected_method: str,
        test_outcome: str,
        explicit_failure_type: str | None = None,
        tokens_used: int = 0,
        tokens_reserved: int = 0,
        evidence_refs: list[str] | None = None,
        snapshot_hash: str | None = None,
    ) -> ExperienceRecord:
        """Create a new OBSERVED experience record."""
        if experience_id in self._records:
            raise ExperienceError(
                f"experience_id already exists: {experience_id}"
            )
        record = ExperienceRecord(
            experience_id=experience_id,
            task_category=task_category,
            input_hash=input_hash,
            snapshot_hash=snapshot_hash,
            policy_epoch=policy_epoch,
            selected_method=selected_method,
            test_outcome=test_outcome,
            explicit_failure_type=explicit_failure_type,
            tokens_used=tokens_used,
            tokens_reserved=tokens_reserved,
            evidence_refs=evidence_refs or [],
            status=ExperienceStatus.OBSERVED,
        )
        self._records[experience_id] = record
        return record

    def transition(
        self,
        experience_id: str,
        target: ExperienceStatus,
        evaluation_evidence: str | None = None,
        owner_approval: str | None = None,
    ) -> ExperienceRecord:
        """Transition an experience record to a new lifecycle status."""
        record = self._records.get(experience_id)
        if record is None:
            raise ExperienceError(
                f"experience not found: {experience_id}"
            )
        current = record.status
        if target not in _VALID_TRANSITIONS.get(current, frozenset()):
            raise ExperienceError(
                f"invalid transition: {current.value} -> {target.value}"
            )
        # Promotion to OWNER_APPROVED requires owner_approval string.
        if target is ExperienceStatus.OWNER_APPROVED and owner_approval is None:
            raise ExperienceError(
                "OWNER_APPROVED requires owner_approval"
            )
        # Promotion to ACTIVE requires complete evaluation.
        if target is ExperienceStatus.ACTIVE:
            if record.evaluation_evidence is None and evaluation_evidence is None:
                raise ExperienceError(
                    "ACTIVE requires evaluation_evidence"
                )
            if record.owner_approval is None:
                raise ExperienceError(
                    "ACTIVE requires OWNER_APPROVED status"
                )
        update: dict[str, Any] = {"status": target}
        if evaluation_evidence is not None:
            update["evaluation_evidence"] = evaluation_evidence
        if owner_approval is not None:
            update["owner_approval"] = owner_approval
        updated = record.model_copy(update=update)
        self._records[experience_id] = updated
        if target is ExperienceStatus.ACTIVE:
            self._active.add(experience_id)
        elif experience_id in self._active:
            self._active.discard(experience_id)
        return updated

    def get(self, experience_id: str) -> ExperienceRecord | None:
        return self._records.get(experience_id)

    def active_records(self) -> list[ExperienceRecord]:
        """Return all ACTIVE experience records."""
        return [
            self._records[eid]
            for eid in sorted(self._active)
        ]

    def is_active(self, experience_id: str) -> bool:
        return experience_id in self._active

    def rollback_target(
        self, experience_id: str
    ) -> str | None:
        """Return the rollback target (previous version) for an active record."""
        record = self._records.get(experience_id)
        if record is None:
            return None
        if record.supersedes:
            return record.supersedes
        return None

    def __len__(self) -> int:
        return len(self._records)

    def all_records(self) -> list[ExperienceRecord]:
        return list(self._records.values())
