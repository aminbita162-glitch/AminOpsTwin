"""Evidence Registry tests (G2.4).

Tests:
    - Put and get with correct key returns the stored entry
    - Epoch mismatch -> entry denied (None)
    - Tenant mismatch -> entry denied (None)
    - Cache binding: tampered entries rejected (G2.4)
      - tampered source_hash
      - tampered claim_span
      - tampered policy_epoch
      - tampered retrieval_window
"""

from __future__ import annotations

import datetime as _dt
import hashlib

import pytest
from aminopstwin.evidence.registry import EvidenceEntry, EvidenceKey, EvidenceRegistry


class TestEvidenceRegistryPutGet:
    """Put and get with correct key."""

    def test_put_and_get_correct_key(self) -> None:
        reg = EvidenceRegistry()
        key = EvidenceKey(
            source_hash="a" * 64,
            claim_span="span-1",
            policy_epoch=0,
            retrieval_window="2026-W01",
        )
        value = {"result": 42, "label": "baseline"}
        created_at = _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)

        entry = reg.put(
            key=key,
            value=value,
            tenant_id="tenant-default",
            pack_hash=None,
            schema_version="1.0",
            snapshot_id="snap-001",
            created_at=created_at,
        )
        assert isinstance(entry, EvidenceEntry)
        assert entry.source_hash == "a" * 64
        assert entry.claim_span == "span-1"
        assert entry.policy_epoch == 0
        assert entry.retrieval_window == "2026-W01"
        assert entry.tenant_id == "tenant-default"
        assert entry.schema_version == "1.0"
        assert entry.snapshot_id == "snap-001"
        assert entry.value == value

        retrieved = reg.get(key, "tenant-default", 0)
        assert retrieved is not None
        assert retrieved.source_hash == entry.source_hash
        assert retrieved.claim_span == entry.claim_span
        assert retrieved.policy_epoch == entry.policy_epoch
        assert retrieved.retrieval_window == entry.retrieval_window
        assert retrieved.value == value

    def test_outer_key_hash_is_64_hex(self) -> None:
        key = EvidenceKey(
            source_hash="b" * 64,
            claim_span="span-2",
            policy_epoch=1,
            retrieval_window="2026-W02",
        )
        okh = EvidenceRegistry.compute_outer_key(key)
        assert len(okh) == 64
        int(okh, 16)  # valid hex

    def test_compute_outer_key_deterministic(self) -> None:
        key = EvidenceKey(
            source_hash="c" * 64,
            claim_span="span-3",
            policy_epoch=2,
            retrieval_window="2026-W03",
        )
        assert EvidenceRegistry.compute_outer_key(key) == (
            EvidenceRegistry.compute_outer_key(key)
        )


class TestEvidenceRegistryEpochMismatch:
    """Epoch mismatch -> entry denied."""

    def test_epoch_mismatch_denied(self) -> None:
        reg = EvidenceRegistry()
        key = EvidenceKey(
            source_hash="d" * 64,
            claim_span="span-4",
            policy_epoch=0,
            retrieval_window="2026-W04",
        )
        reg.put(
            key=key,
            value={"x": 1},
            tenant_id="tenant-default",
            pack_hash=None,
            schema_version="1.0",
            snapshot_id="snap-004",
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        # Request with epoch 1 while entry was stored at epoch 0
        result = reg.get(key, "tenant-default", 1)
        assert result is None


class TestEvidenceRegistryTenantMismatch:
    """Tenant mismatch -> entry denied."""

    def test_tenant_mismatch_denied(self) -> None:
        reg = EvidenceRegistry()
        key = EvidenceKey(
            source_hash="e" * 64,
            claim_span="span-5",
            policy_epoch=0,
            retrieval_window="2026-W05",
        )
        reg.put(
            key=key,
            value={"x": 2},
            tenant_id="tenant-default",
            pack_hash=None,
            schema_version="1.0",
            snapshot_id="snap-005",
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        result = reg.get(key, "tenant-other", 0)
        assert result is None


class TestEvidenceRegistryTamperDetection:
    """Cache binding: tampered entries rejected (G2.4).

    Each test stores an entry, then simulates a tampered key and
    verifies that get returns None.
    """

    def _make_registry_with_entry(self) -> tuple[EvidenceRegistry, EvidenceKey]:
        reg = EvidenceRegistry()
        key = EvidenceKey(
            source_hash="f" * 64,
            claim_span="span-6",
            policy_epoch=0,
            retrieval_window="2026-W06",
        )
        reg.put(
            key=key,
            value={"result": 100},
            tenant_id="tenant-default",
            pack_hash=None,
            schema_version="1.0",
            snapshot_id="snap-006",
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        return reg, key

    def test_tampered_source_hash_rejected(self) -> None:
        reg, key = self._make_registry_with_entry()
        tampered = EvidenceKey(
            source_hash="a" * 64,  # different source_hash
            claim_span=key.claim_span,
            policy_epoch=key.policy_epoch,
            retrieval_window=key.retrieval_window,
        )
        # The tampered key produces a different outer_key_hash, so
        # the store lookup misses. Additionally, even if we directly
        # query the stored entry's outer key with the tampered key,
        # the cache binding check catches the mismatch.
        assert reg.get(tampered, "tenant-default", 0) is None

    def test_tampered_claim_span_rejected(self) -> None:
        reg, key = self._make_registry_with_entry()
        tampered = EvidenceKey(
            source_hash=key.source_hash,
            claim_span="tampered-span",
            policy_epoch=key.policy_epoch,
            retrieval_window=key.retrieval_window,
        )
        assert reg.get(tampered, "tenant-default", 0) is None

    def test_tampered_policy_epoch_rejected(self) -> None:
        reg, key = self._make_registry_with_entry()
        tampered = EvidenceKey(
            source_hash=key.source_hash,
            claim_span=key.claim_span,
            policy_epoch=99,
            retrieval_window=key.retrieval_window,
        )
        assert reg.get(tampered, "tenant-default", 0) is None

    def test_tampered_retrieval_window_rejected(self) -> None:
        reg, key = self._make_registry_with_entry()
        tampered = EvidenceKey(
            source_hash=key.source_hash,
            claim_span=key.claim_span,
            policy_epoch=key.policy_epoch,
            retrieval_window="2026-TAMPER",
        )
        assert reg.get(tampered, "tenant-default", 0) is None

    def test_direct_field_tamper_detected(self) -> None:
        """Simulate direct tampering of a stored entry's fields.

        Even if an attacker modifies the stored entry's source_hash
        directly in the store dict, the get() method detects the
        mismatch because the outer_key_hash was computed from the
        original key, not the tampered entry.
        """
        reg = EvidenceRegistry()
        key = EvidenceKey(
            source_hash="0a" * 32,
            claim_span="span-7",
            policy_epoch=0,
            retrieval_window="2026-W07",
        )
        reg.put(
            key=key,
            value={"v": 1},
            tenant_id="tenant-default",
            pack_hash=None,
            schema_version="1.0",
            snapshot_id="snap-007",
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )

        # Get the original entry back
        original = reg.get(key, "tenant-default", 0)
        assert original is not None

        # Simulate direct tampering: replace the stored entry with one
        # that has a different source_hash but same outer_key_hash.
        tampered_hash = "1b" * 32  # different valid hex source_hash
        tampered_entry = EvidenceEntry(
            evidence_key=EvidenceKey(
                source_hash=tampered_hash,
                claim_span=key.claim_span,
                policy_epoch=key.policy_epoch,
                retrieval_window=key.retrieval_window,
            ),
            outer_key_hash=original.outer_key_hash,  # same outer key
            source_hash=tampered_hash,  # tampered
            claim_span=key.claim_span,
            policy_epoch=0,
            retrieval_window=key.retrieval_window,
            tenant_id="tenant-default",
            pack_hash=None,
            schema_version="1.0",
            snapshot_id="snap-007",
            value={"v": 1},
            value_hash=original.value_hash,
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        # Inject the tampered entry into the store
        reg._store[original.outer_key_hash] = tampered_entry

        # Now get() with the original key should detect the mismatch
        # because entry.source_hash != key.source_hash
        result = reg.get(key, "tenant-default", 0)
        assert result is None

    def test_value_hash_matches_canonical(self) -> None:
        """value_hash is SHA-256 of canonical bytes of the value dict."""
        reg = EvidenceRegistry()
        key = EvidenceKey(
            source_hash="2c" * 32,
            claim_span="span-8",
            policy_epoch=0,
            retrieval_window="2026-W08",
        )
        value = {"a": 1, "b": [1, 2, 3], "c": "hello"}
        entry = reg.put(
            key=key,
            value=value,
            tenant_id="tenant-default",
            pack_hash=None,
            schema_version="1.0",
            snapshot_id="snap-008",
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        import json

        expected = hashlib.sha256(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        assert entry.value_hash == expected


def test_evidence_key_frozen() -> None:
    """EvidenceKey is frozen — assignment raises ValidationError."""
    from pydantic import ValidationError

    key = EvidenceKey(
        source_hash="3d" * 32,
        claim_span="span-9",
        policy_epoch=0,
        retrieval_window="2026-W09",
    )
    with pytest.raises(ValidationError):
        key.source_hash = "4e" * 32  # type: ignore[misc]


def test_evidence_entry_frozen() -> None:
    """EvidenceEntry is frozen — assignment raises ValidationError."""
    from pydantic import ValidationError

    key = EvidenceKey(
        source_hash="5f" * 32,
        claim_span="span-10",
        policy_epoch=0,
        retrieval_window="2026-W10",
    )
    entry = EvidenceEntry(
        evidence_key=key,
        outer_key_hash="6a" * 32,
        source_hash="5f" * 32,
        claim_span="span-10",
        policy_epoch=0,
        retrieval_window="2026-W10",
        tenant_id="tenant-default",
        pack_hash=None,
        schema_version="1.0",
        snapshot_id="snap-010",
        value={"v": 1},
        value_hash="7b" * 32,
        created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
    )
    with pytest.raises(ValidationError):
        entry.source_hash = "8c" * 32  # type: ignore[misc]
