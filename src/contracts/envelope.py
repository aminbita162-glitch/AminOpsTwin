"""Envelope contract (§3.5) — typed, versioned inter-component message format.

Every inter-component message is an Envelope (Pydantic v2, extra="forbid",
frozen=True, strict=True). The model is normative; names, types, and
constraints are exact.

NO issuer field (§3.5.1): the identity of the caller is NOT a message field.
The caller's principal (A1..A5, S1, S2) is assigned by the runtime.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    field_serializer,
    field_validator,
    model_validator,
)

from .canonical import canonical_hash
from .clock import format_rfc3339_z

__all__ = ["Envelope", "EnvelopeError"]


class EnvelopeError(ValueError):
    """Raised when an Envelope fails construction or validation."""


# Regex patterns (§3.5)
_SCHEMA_ID_PATTERN = re.compile(r"^[a-z0-9_.]{1,64}@[0-9]{1,4}$")
_ENVELOPE_TYPE_PATTERN = re.compile(r"^[a-z0-9_.]{1,64}$")
_TENANT_ID_PATTERN = re.compile(r"^[a-z0-9-]{1,64}$")
_IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_PAYLOAD_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

# Forbidden key: "issuer" must never appear anywhere in the payload (§3.5.1).
_FORBIDDEN_KEYS: frozenset[str] = frozenset({"issuer"})


class Envelope(BaseModel):
    """Typed, versioned inter-component message envelope (§3.5).

    model_config: extra="forbid", frozen=True, strict=True.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_assignment=True,
    )

    envelope_version: Literal["1.0"]
    schema_id: str
    envelope_type: str
    correlation_id: uuid.UUID
    causation_id: uuid.UUID | None
    tenant_id: str
    policy_epoch: int
    idempotency_key: str
    payload: dict[str, Any]
    payload_hash: str
    created_at: datetime

    # --- Validators ---

    @field_validator("schema_id")
    @classmethod
    def _validate_schema_id(cls, v: str) -> str:
        if not _SCHEMA_ID_PATTERN.match(v):
            raise ValueError(
                f"schema_id must match {_SCHEMA_ID_PATTERN.pattern}"
            )
        return v

    @field_validator("envelope_type")
    @classmethod
    def _validate_envelope_type(cls, v: str) -> str:
        if not _ENVELOPE_TYPE_PATTERN.match(v):
            raise ValueError(
                f"envelope_type must match "
                f"{_ENVELOPE_TYPE_PATTERN.pattern}"
            )
        return v

    @field_validator("tenant_id")
    @classmethod
    def _validate_tenant_id(cls, v: str) -> str:
        if not _TENANT_ID_PATTERN.match(v):
            raise ValueError(
                f"tenant_id must match {_TENANT_ID_PATTERN.pattern}"
            )
        return v

    @field_validator("idempotency_key")
    @classmethod
    def _validate_idempotency_key(cls, v: str) -> str:
        if not _IDEMPOTENCY_KEY_PATTERN.match(v):
            raise ValueError(
                f"idempotency_key must match "
                f"{_IDEMPOTENCY_KEY_PATTERN.pattern}"
            )
        return v

    @field_validator("policy_epoch")
    @classmethod
    def _validate_policy_epoch(cls, v: int) -> int:
        if v < 0:
            raise ValueError("policy_epoch must be >= 0")
        return v

    @field_validator("payload_hash")
    @classmethod
    def _validate_payload_hash(cls, v: str) -> str:
        if not _PAYLOAD_HASH_PATTERN.match(v):
            raise ValueError(
                "payload_hash must be a 64-char lowercase hex SHA-256"
            )
        return v

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at must be timezone-aware (UTC)")
        return v

    @field_validator("payload")
    @classmethod
    def _validate_payload_no_issuer(
        cls, v: dict[str, Any]
    ) -> dict[str, Any]:
        """Reject the forbidden 'issuer' key anywhere in the payload."""
        _check_no_issuer(v)
        return v

    @model_validator(mode="after")
    def _validate_payload_hash_matches(self) -> Envelope:
        """Verify payload_hash matches the recomputed canonical hash."""
        recomputed = canonical_hash(self.payload)
        if recomputed != self.payload_hash:
            raise ValueError(
                f"payload_hash mismatch: expected {recomputed}, "
                f"got {self.payload_hash}"
            )
        return self

    @field_serializer("created_at")
    def _serialize_created_at(self, v: datetime) -> str:
        return format_rfc3339_z(v)

    @field_serializer("correlation_id")
    def _serialize_correlation_id(self, v: uuid.UUID) -> str:
        return str(v)

    @field_serializer("causation_id")
    def _serialize_causation_id(
        self, v: uuid.UUID | None
    ) -> str | None:
        return str(v) if v is not None else None


def _check_no_issuer(obj: Any) -> None:
    """Recursively check that no 'issuer' key exists anywhere in the payload."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in _FORBIDDEN_KEYS:
                raise ValueError(
                    "forbidden key 'issuer' in payload (§3.5.1)"
                )
            _check_no_issuer(value)
    elif isinstance(obj, list):
        for item in obj:
            _check_no_issuer(item)
