"""G4.2 — Source rights and provenance tests (P4, §30, G4.2).

100% of active source versions have complete approval, provenance and
rights records. Every unapproved/unknown-license fixture is excluded
from activation.
"""

from __future__ import annotations

import hashlib

import pytest
from aminopstwin.evidence.source_rights import (
    SourceRecord,
    SourceRegistry,
    SourceRegistryError,
    SourceStatus,
)


def _make_source(
    source_id: str = "src-001",
    status: SourceStatus = SourceStatus.DISCOVERED,
    content_sha256: str = "",
) -> SourceRecord:
    if not content_sha256:
        content_sha256 = hashlib.sha256(b"test content").hexdigest()
    return SourceRecord(
        source_id=source_id,
        title="Operational Queueing Research",
        publisher="PMC Open Access Subset",
        license="CC-BY",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        retrieved_at="2026-10-23T00:00:00Z",
        content_sha256=content_sha256,
        permitted_use="operational research reference",
        owner_approval_date="2026-10-23",
        status=status,
    )


class TestSourceRegistryLifecycle:
    """Source lifecycle: DISCOVERED -> REVIEW_PENDING -> APPROVED -> ACTIVE."""

    def test_register_creates_discovered(self) -> None:
        reg = SourceRegistry()
        record = _make_source()
        reg.register(record)
        got = reg.get("src-001")
        assert got is not None
        assert got.status is SourceStatus.DISCOVERED

    def test_duplicate_register_rejected(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        with pytest.raises(SourceRegistryError):
            reg.register(_make_source())

    def test_register_non_discovered_rejected(self) -> None:
        reg = SourceRegistry()
        record = _make_source(status=SourceStatus.ACTIVE)
        with pytest.raises(SourceRegistryError):
            reg.register(record)

    def test_full_lifecycle_to_active(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        reg.transition("src-001", SourceStatus.ACTIVE)
        assert reg.is_active("src-001")
        assert reg.is_approved("src-001")

    def test_invalid_transition_rejected(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        with pytest.raises(SourceRegistryError):
            reg.transition("src-001", SourceStatus.ACTIVE)

    def test_active_to_superseded(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        reg.transition("src-001", SourceStatus.ACTIVE)
        reg.transition("src-001", SourceStatus.SUPERSEDED, reason="replaced")
        assert not reg.is_active("src-001")

    def test_active_to_quarantined(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        reg.transition("src-001", SourceStatus.ACTIVE)
        reg.transition("src-001", SourceStatus.QUARANTINED, reason="license issue")
        assert not reg.is_active("src-001")
        assert not reg.is_approved("src-001")

    def test_active_to_retired(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        reg.transition("src-001", SourceStatus.ACTIVE)
        reg.transition("src-001", SourceStatus.RETIRED, reason="deprecated")
        assert not reg.is_active("src-001")


class TestSourceCacheAdmission:
    """G4.2: unapproved/unknown-license fixtures excluded from activation."""

    def test_discovered_not_admitted(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        assert not reg.admit_to_cache("src-001")

    def test_review_pending_not_admitted(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        assert not reg.admit_to_cache("src-001")

    def test_approved_admitted(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        assert reg.admit_to_cache("src-001")

    def test_active_admitted(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        reg.transition("src-001", SourceStatus.ACTIVE)
        assert reg.admit_to_cache("src-001")

    def test_superseded_not_admitted(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        reg.transition("src-001", SourceStatus.ACTIVE)
        reg.transition("src-001", SourceStatus.SUPERSEDED)
        assert not reg.admit_to_cache("src-001")

    def test_quarantined_not_admitted(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        reg.transition("src-001", SourceStatus.ACTIVE)
        reg.transition("src-001", SourceStatus.QUARANTINED)
        assert not reg.admit_to_cache("src-001")

    def test_retired_not_admitted(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        reg.transition("src-001", SourceStatus.ACTIVE)
        reg.transition("src-001", SourceStatus.RETIRED)
        assert not reg.admit_to_cache("src-001")

    def test_unregistered_not_admitted(self) -> None:
        reg = SourceRegistry()
        assert not reg.admit_to_cache("nonexistent")


class TestSourceProvenanceFields:
    """Source records have complete extended provenance fields (§30.3)."""

    def test_extended_fields_present(self) -> None:
        record = _make_source()
        assert record.document_version is not None
        assert record.language is not None
        assert record.commercial_use_status is not None
        assert record.redistribution_status is not None
        assert record.machine_retrieval_status is not None
        assert record.review_status is not None

    def test_content_hash_computation(self) -> None:
        content = b"test content for hashing"
        expected = hashlib.sha256(content).hexdigest()
        assert SourceRegistry.compute_content_hash(content) == expected

    def test_content_hash_for_approved_source(self) -> None:
        reg = SourceRegistry()
        sha = hashlib.sha256(b"content").hexdigest()
        reg.register(_make_source(content_sha256=sha))
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        assert reg.content_hash("src-001") == sha

    def test_content_hash_none_for_unapproved(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source())
        assert reg.content_hash("src-001") is None

    def test_content_hash_none_for_unregistered(self) -> None:
        reg = SourceRegistry()
        assert reg.content_hash("nonexistent") is None

    def test_all_records_returns_all(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source("src-001"))
        reg.register(_make_source("src-002"))
        assert len(reg.all_records()) == 2

    def test_approved_records_filters(self) -> None:
        reg = SourceRegistry()
        reg.register(_make_source("src-001"))
        reg.register(_make_source("src-002"))
        reg.transition("src-001", SourceStatus.REVIEW_PENDING)
        reg.transition("src-001", SourceStatus.APPROVED)
        approved = reg.approved_records()
        assert len(approved) == 1
        assert approved[0].source_id == "src-001"
