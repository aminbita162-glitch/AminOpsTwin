"""Evidence Registry with cache binding (§3.10, G2.4).

The Evidence Registry stores evidence entries keyed by a cryptographic
outer key derived from the EvidenceKey components. Cache binding ensures
that any tampering with source_hash, claim_span, policy_epoch, or
retrieval_window after storage is detected and the entry is rejected
(GW-EVID-001).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "EvidenceKey",
    "EvidenceEntry",
    "EvidenceRegistry",
]

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class EvidenceKey(BaseModel):
    """Cryptographic key for evidence cache binding (§3.10).

    model_config: frozen, strict, extra="forbid".
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    source_hash: str  # 64-char hex SHA-256
    claim_span: str
    policy_epoch: int = Field(ge=0)
    retrieval_window: str

    @field_validator("source_hash")
    @classmethod
    def _validate_source_hash(cls, v: str) -> str:
        if not _HEX64_RE.match(v):
            raise ValueError(
                "source_hash must be a 64-char lowercase hex SHA-256"
            )
        return v


class EvidenceEntry(BaseModel):
    """A single stored evidence entry (§3.10).

    model_config: frozen, strict, extra="forbid".
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    evidence_key: EvidenceKey
    outer_key_hash: str  # 64-char hex SHA-256
    source_hash: str
    claim_span: str
    policy_epoch: int = Field(ge=0)
    retrieval_window: str
    tenant_id: str
    pack_hash: str | None = None
    schema_version: str
    snapshot_id: str
    value: dict[str, Any]
    value_hash: str  # 64-char hex SHA-256
    created_at: _dt.datetime

    @field_validator("outer_key_hash")
    @classmethod
    def _validate_outer_key_hash(cls, v: str) -> str:
        if not _HEX64_RE.match(v):
            raise ValueError(
                "outer_key_hash must be a 64-char lowercase hex SHA-256"
            )
        return v

    @field_validator("source_hash")
    @classmethod
    def _validate_source_hash(cls, v: str) -> str:
        if not _HEX64_RE.match(v):
            raise ValueError(
                "source_hash must be a 64-char lowercase hex SHA-256"
            )
        return v

    @field_validator("value_hash")
    @classmethod
    def _validate_value_hash(cls, v: str) -> str:
        if not _HEX64_RE.match(v):
            raise ValueError(
                "value_hash must be a 64-char lowercase hex SHA-256"
            )
        return v

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, v: _dt.datetime) -> _dt.datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v


class EvidenceRegistry:
    """In-memory evidence registry with cache binding (G2.4).

    Stores EvidenceEntry objects keyed by their outer_key_hash.
    On retrieval, verifies that the entry's source_hash, claim_span,
    policy_epoch, and retrieval_window match the EvidenceKey — any
    mismatch indicates tampering and the entry is rejected (G2.4).
    """

    def __init__(self) -> None:
        self._store: dict[str, EvidenceEntry] = {}

    @staticmethod
    def compute_outer_key(key: EvidenceKey) -> str:
        """Compute the SHA-256 outer key from an EvidenceKey.

        The hash is taken over the canonical bytes of the EvidenceKey
        components: source_hash, claim_span, policy_epoch,
        retrieval_window.
        """
        canonical = json.dumps(
            {
                "source_hash": key.source_hash,
                "claim_span": key.claim_span,
                "policy_epoch": key.policy_epoch,
                "retrieval_window": key.retrieval_window,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def put(
        self,
        key: EvidenceKey,
        value: dict[str, Any],
        tenant_id: str,
        pack_hash: str | None,
        schema_version: str,
        snapshot_id: str,
        created_at: _dt.datetime,
    ) -> EvidenceEntry:
        """Store an evidence entry and return it.

        Computes the value_hash from the canonical bytes of *value*,
        and the outer_key_hash from the EvidenceKey.
        """
        value_hash = hashlib.sha256(
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

        outer_key_hash = self.compute_outer_key(key)

        entry = EvidenceEntry(
            evidence_key=key,
            outer_key_hash=outer_key_hash,
            source_hash=key.source_hash,
            claim_span=key.claim_span,
            policy_epoch=key.policy_epoch,
            retrieval_window=key.retrieval_window,
            tenant_id=tenant_id,
            pack_hash=pack_hash,
            schema_version=schema_version,
            snapshot_id=snapshot_id,
            value=value,
            value_hash=value_hash,
            created_at=created_at,
        )
        self._store[outer_key_hash] = entry
        return entry

    def get(
        self,
        key: EvidenceKey,
        tenant_id: str,
        current_epoch: int,
    ) -> EvidenceEntry | None:
        """Retrieve an evidence entry by key.

        Returns the entry if:
            - the outer key matches the stored entry's outer_key_hash
            - the tenant_id matches
            - the current_epoch matches the entry's policy_epoch
            - the source_hash, claim_span, policy_epoch, and
              retrieval_window match the EvidenceKey (cache binding, G2.4)

        Returns None (denied) if any check fails.
        """
        outer_key_hash = self.compute_outer_key(key)
        entry = self._store.get(outer_key_hash)
        if entry is None:
            return None

        # Tenant match check (GW-TENANT-001)
        if entry.tenant_id != tenant_id:
            return None

        # Epoch match check (GW-EPOCH-001)
        if entry.policy_epoch != current_epoch:
            return None

        # Cache binding: verify the entry's bound fields match the key
        # (G2.4, GW-EVID-001). If any of source_hash, claim_span,
        # policy_epoch, or retrieval_window were tampered, reject.
        if (
            entry.source_hash != key.source_hash
            or entry.claim_span != key.claim_span
            or entry.policy_epoch != key.policy_epoch
            or entry.retrieval_window != key.retrieval_window
        ):
            return None

        return entry

    def __len__(self) -> int:
        return len(self._store)
