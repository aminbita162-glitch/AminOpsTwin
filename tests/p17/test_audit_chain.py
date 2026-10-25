"""G17.3 — Audit Hash-Chain: prev_hash, record_hash, tamper detection (P17).

Tests that the audit chain correctly links records via prev_hash /
record_hash, detects tampering, and that the offline CLI verifies the
chain.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aminopstwin.evidence.audit_chain import (
    AuditChain,
    AuditRecord,
    canonical_record_bytes,
    compute_record_hash,
    verify_chain,
)
from aminopstwin.evidence.temporal_versioning import (
    ClaimHistory,
    ClaimVersion,
    TemporalRegistry,
)


class TestAuditChain:
    """G17.3: audit hash-chain with tamper detection."""

    def test_append_and_verify(self) -> None:
        """A simple chain appends records and verifies clean."""
        chain = AuditChain()
        chain.append(timestamp=100, event="start", payload={"a": 1})
        chain.append(timestamp=200, event="step", payload={"b": 2})
        chain.append(timestamp=300, event="end", payload={})

        assert chain.length == 3
        assert verify_chain(chain.records) == []

    def test_genesis_prev_hash(self) -> None:
        """The first record has prev_hash = all zeros."""
        chain = AuditChain()
        chain.append(timestamp=100, event="genesis", payload={})
        assert chain.records[0].prev_hash == "0" * 64

    def test_prev_hash_links(self) -> None:
        """Each record's prev_hash matches the previous record_hash."""
        chain = AuditChain()
        chain.append(timestamp=100, event="a", payload={})
        chain.append(timestamp=200, event="b", payload={})
        assert chain.records[1].prev_hash == chain.records[0].record_hash

    def test_record_hash_is_deterministic(self) -> None:
        """The same inputs produce the same record_hash."""
        chain1 = AuditChain()
        chain1.append(timestamp=100, event="test", payload={"k": 1})
        chain2 = AuditChain()
        chain2.append(timestamp=100, event="test", payload={"k": 1})
        assert chain1.records[0].record_hash == chain2.records[0].record_hash

    def test_tampering_detected(self) -> None:
        """Tampering with a record's payload breaks the chain."""
        chain = AuditChain()
        chain.append(timestamp=100, event="a", payload={"x": 1})
        chain.append(timestamp=200, event="b", payload={"y": 2})
        chain.append(timestamp=300, event="c", payload={"z": 3})

        # Tamper: modify the second record's payload.
        records = chain.records
        tampered = AuditRecord(
            record_id=records[1].record_id,
            prev_hash=records[1].prev_hash,
            record_hash=records[1].record_hash,
            timestamp=records[1].timestamp,
            event=records[1].event,
            payload={"TAMPERED": True},  # different payload
        )
        tampered_records = [records[0], tampered, records[2]]
        broken = verify_chain(tampered_records)
        # Record 2's hash no longer matches the recomputed hash.
        assert 2 in broken

    def test_tampering_prev_hash_detected(self) -> None:
        """Tampering with prev_hash breaks the chain."""
        chain = AuditChain()
        chain.append(timestamp=100, event="a", payload={})
        chain.append(timestamp=200, event="b", payload={})
        records = chain.records
        tampered = AuditRecord(
            record_id=records[1].record_id,
            prev_hash="f" * 64,  # wrong prev_hash
            record_hash=records[1].record_hash,
            timestamp=records[1].timestamp,
            event=records[1].event,
            payload=records[1].payload,
        )
        broken = verify_chain([records[0], tampered])
        assert 2 in broken

    def test_tampering_record_id_detected(self) -> None:
        """A non-sequential record_id breaks the chain."""
        chain = AuditChain()
        chain.append(timestamp=100, event="a", payload={})
        chain.append(timestamp=200, event="b", payload={})
        records = chain.records
        tampered = AuditRecord(
            record_id=99,  # wrong ID
            prev_hash=records[1].prev_hash,
            record_hash=records[1].record_hash,
            timestamp=records[1].timestamp,
            event=records[1].event,
            payload=records[1].payload,
        )
        broken = verify_chain([records[0], tampered])
        assert 99 in broken

    def test_checkpoint_with_signing_key(self) -> None:
        """A checkpoint with a signing key produces _signed records."""
        chain = AuditChain(signing_key="secret-key")
        chain.append(timestamp=100, event="start", payload={})
        chain.checkpoint(timestamp=200)

        assert chain.length == 2
        # The chain verifies with the signing key.
        assert verify_chain(chain.records, signing_key="secret-key") == []

        # Without the signing key, the checkpoint record fails.
        broken = verify_chain(chain.records, signing_key=None)
        # The checkpoint record (ID 2) should fail because _signed is
        # in the body when signing_key is provided.
        assert 2 in broken

    def test_serialization_roundtrip(self, tmp_path: Path) -> None:
        """save/load round-trips the chain."""
        chain = AuditChain()
        chain.append(timestamp=100, event="a", payload={"k": 1})
        chain.append(timestamp=200, event="b", payload={"k": 2})
        path = tmp_path / "audit.json"
        chain.save(path)

        loaded = AuditChain.load(path)
        assert loaded.length == 2
        assert loaded.records[0].record_hash == chain.records[0].record_hash
        assert verify_chain(loaded.records) == []

    def test_to_list_from_list_roundtrip(self) -> None:
        """to_list / from_list round-trips the chain."""
        chain = AuditChain()
        chain.append(timestamp=100, event="a", payload={"x": [1, 2]})
        chain.append(timestamp=200, event="b", payload={"y": {"z": 3}})

        data = chain.to_list()
        json_str = json.dumps(data)
        data2 = json.loads(json_str)
        loaded = AuditChain.from_list(data2)

        assert loaded.length == chain.length
        assert loaded.records[0].record_hash == chain.records[0].record_hash
        assert verify_chain(loaded.records) == []

    def test_compute_record_hash(self) -> None:
        """compute_record_hash is deterministic."""
        body = {"timestamp": 100, "event": "test", "payload": {"k": 1}}
        h1 = compute_record_hash("0" * 64, body)
        h2 = compute_record_hash("0" * 64, body)
        assert h1 == h2
        assert len(h1) == 64

    def test_canonical_record_bytes(self) -> None:
        """canonical_record_bytes produces sorted, compact JSON."""
        body = {"b": 2, "a": 1}
        b = canonical_record_bytes({"body": body, "prev_hash": "0" * 64})
        # Keys should be sorted.
        text = b.decode("utf-8")
        assert text.index('"a"') < text.index('"b"')
        assert text.index('"body"') < text.index('"prev_hash"')

    def test_empty_chain_verifies(self) -> None:
        """An empty chain verifies (trivially)."""
        chain = AuditChain()
        assert verify_chain(chain.records) == []
        assert chain.head_hash == "0" * 64

    def test_head_hash_after_appends(self) -> None:
        """head_hash returns the last record's hash."""
        chain = AuditChain()
        chain.append(timestamp=100, event="a", payload={})
        assert chain.head_hash == chain.records[-1].record_hash
        chain.append(timestamp=200, event="b", payload={})
        assert chain.head_hash == chain.records[-1].record_hash


class TestTemporalVersioning:
    """G17.3: temporal versioning — append-only claim history."""

    def test_record_and_retrieve(self) -> None:
        """Recording a version makes it retrievable."""
        registry = TemporalRegistry()
        registry.record("C1", "hash_a", 100, "evidence.txt")
        assert registry.get_current_hash("C1") == "hash_a"
        assert registry.get_hash_at_version("C1", 1) == "hash_a"

    def test_prior_hash_after_update(self) -> None:
        """After an update, the prior hash is still retrievable."""
        registry = TemporalRegistry()
        registry.record("C1", "hash_a", 100, "evidence.txt")
        registry.record("C1", "hash_b", 200, "evidence.txt")

        assert registry.get_current_hash("C1") == "hash_b"
        assert registry.get_prior_hash("C1") == "hash_a"
        assert registry.get_hash_at_version("C1", 1) == "hash_a"
        assert registry.get_hash_at_version("C1", 2) == "hash_b"

    def test_multiple_claims(self) -> None:
        """Multiple claims maintain independent histories."""
        registry = TemporalRegistry()
        registry.record("C1", "hash_1a", 100, "e1.txt")
        registry.record("C2", "hash_2a", 100, "e2.txt")
        registry.record("C1", "hash_1b", 200, "e1.txt")

        assert registry.get_current_hash("C1") == "hash_1b"
        assert registry.get_current_hash("C2") == "hash_2a"
        assert registry.get_prior_hash("C1") == "hash_1a"
        assert registry.get_prior_hash("C2") is None

    def test_append_only_history(self) -> None:
        """The history list only grows — prior versions are preserved."""
        registry = TemporalRegistry()
        for i in range(5):
            registry.record("C1", f"hash_v{i + 1}", 100 + i, "e.txt")

        history = registry.get_history("C1")
        assert history is not None
        assert len(history.versions) == 5
        for i, v in enumerate(history.versions):
            assert v.version == i + 1
            assert v.hash == f"hash_v{i + 1}"

    def test_history_to_dict_from_dict(self) -> None:
        """ClaimHistory serializes and deserializes."""
        history = ClaimHistory(claim_id="C1")
        history.add_version("hash_a", 100, "e.txt")
        history.add_version("hash_b", 200, "e.txt")

        d = history.to_dict()
        json_str = json.dumps(d)
        d2 = json.loads(json_str)
        history2 = ClaimHistory.from_dict(d2)
        assert len(history2.versions) == 2
        assert history2.versions[0].hash == "hash_a"
        assert history2.versions[1].hash == "hash_b"

    def test_registry_to_dict_from_dict(self) -> None:
        """TemporalRegistry serializes and deserializes."""
        registry = TemporalRegistry()
        registry.record("C1", "hash_a", 100, "e1.txt")
        registry.record("C2", "hash_b", 200, "e2.txt")

        d = registry.to_dict()
        json_str = json.dumps(d)
        d2 = json.loads(json_str)
        registry2 = TemporalRegistry.from_dict(d2)
        assert registry2.get_current_hash("C1") == "hash_a"
        assert registry2.get_current_hash("C2") == "hash_b"

    def test_registry_save_load(self, tmp_path: Path) -> None:
        """TemporalRegistry save/load round-trips."""
        registry = TemporalRegistry()
        registry.record("C1", "hash_a", 100, "e.txt")
        registry.record("C1", "hash_b", 200, "e.txt")

        path = tmp_path / "temporal.json"
        registry.save(path)

        loaded = TemporalRegistry.load(path)
        assert loaded.get_current_hash("C1") == "hash_b"
        assert loaded.get_prior_hash("C1") == "hash_a"
        assert loaded.get_hash_at_version("C1", 1) == "hash_a"

    def test_get_nonexistent_claim(self) -> None:
        """Retrieving a non-existent claim returns None."""
        registry = TemporalRegistry()
        assert registry.get_current_hash("NONEXIST") is None
        assert registry.get_prior_hash("NONEXIST") is None
        assert registry.get_history("NONEXIST") is None
        assert registry.get_hash_at_version("NONEXIST", 1) is None

    def test_claim_ids_sorted(self) -> None:
        """claim_ids returns sorted list."""
        registry = TemporalRegistry()
        registry.record("C3", "h", 100, "e.txt")
        registry.record("C1", "h", 100, "e.txt")
        registry.record("C2", "h", 100, "e.txt")
        assert registry.claim_ids == ["C1", "C2", "C3"]

    def test_claim_version_immutable(self) -> None:
        """ClaimVersion is frozen."""
        cv = ClaimVersion(
            claim_id="C1", version=1, hash="h", recorded_at=100, evidence_path="e.txt",
        )
        with pytest.raises(AttributeError):
            cv.hash = "different"  # type: ignore[misc]

    def test_multiple_versions_prior_hash_chain(self) -> None:
        """A chain of 3 versions: prior_hash returns v2's hash at v3."""
        registry = TemporalRegistry()
        registry.record("C1", "v1", 100, "e.txt")
        registry.record("C1", "v2", 200, "e.txt")
        registry.record("C1", "v3", 300, "e.txt")
        assert registry.get_prior_hash("C1") == "v2"
        assert registry.get_current_hash("C1") == "v3"
