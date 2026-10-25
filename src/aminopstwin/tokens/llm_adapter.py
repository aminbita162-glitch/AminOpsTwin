"""LLM Adapter — record/replay with zero live network calls (§24.2, G2.10).

The LLM Adapter is the only component that talks to LLM APIs. In test
mode it uses pre-recorded responses looked up by request_hash. If no
recording is found, it raises ReplayMissError — it NEVER falls through to
a live network call (G2.10).

LLMRecord captures the full record/replay contract (§24.2):
    record_id, request_hash, response, response_hash, model_id,
    adapter_version, expected_schema_id, tokens_input, tokens_output,
    recorded_at.

compute_request_hash produces a deterministic SHA-256 over the canonical
bytes of (adapter_version, model_id, params, messages).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aminopstwin.contracts.clock import Clock

__all__ = ["LLMRecord", "LLMAdapter", "ReplayMissError"]


class ReplayMissError(Exception):
    """Raised when no recording matches the request_hash in replay mode."""


class LLMRecord(BaseModel):
    """Record/replay entry for a single LLM call (§24.2).

    model_config: frozen, strict, extra="forbid".
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    record_id: str
    request_hash: str  # 64-char hex SHA-256
    response: str
    response_hash: str  # 64-char hex SHA-256
    model_id: str
    adapter_version: str
    expected_schema_id: str
    tokens_input: int = Field(ge=0)
    tokens_output: int = Field(ge=0)
    recorded_at: _dt.datetime

    @field_validator("request_hash")
    @classmethod
    def _validate_request_hash(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError(
                "request_hash must be a 64-char lowercase hex SHA-256"
            )
        return v

    @field_validator("response_hash")
    @classmethod
    def _validate_response_hash(cls, v: str) -> str:
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError(
                "response_hash must be a 64-char lowercase hex SHA-256"
            )
        return v

    @field_validator("recorded_at")
    @classmethod
    def _validate_recorded_at(cls, v: _dt.datetime) -> _dt.datetime:
        if v.tzinfo is None:
            raise ValueError("recorded_at must be timezone-aware (UTC)")
        return v


class LLMAdapter:
    """Record/replay LLM adapter with zero live network calls (G2.10).

    In test mode (recordings_dir is not None), call() looks up a
    recording by request_hash. If no recording is found, it raises
    ReplayMissError. It NEVER falls through to a live network call.
    """

    def __init__(
        self,
        adapter_version: str,
        model_id: str,
        recordings_dir: Path | None = None,
    ) -> None:
        self._adapter_version = adapter_version
        self._model_id = model_id
        self._recordings_dir = recordings_dir
        self._recordings: dict[str, LLMRecord] = {}
        if recordings_dir is not None and recordings_dir.exists():
            self._load_recordings(recordings_dir)

    def _load_recordings(self, recordings_dir: Path) -> None:
        """Load all recordings from a directory."""
        for path in recordings_dir.glob("*.json"):
            with path.open() as f:
                data = json.load(f)
            # Parse datetime strings back to datetime objects
            if isinstance(data.get("recorded_at"), str):
                data["recorded_at"] = _dt.datetime.fromisoformat(
                    data["recorded_at"].replace("Z", "+00:00")
                )
            record = LLMRecord(**data)
            self._recordings[record.request_hash] = record

    @staticmethod
    def compute_request_hash(
        adapter_version: str,
        model_id: str,
        params: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> str:
        """Compute the SHA-256 request hash over canonical bytes.

        The hash is taken over:
            json.dumps({
                "adapter_version": adapter_version,
                "model_id": model_id,
                "params": params,
                "messages": messages,
            }, sort_keys=True, separators=(',', ':'),
            ensure_ascii=False, allow_nan=False).encode('utf-8')
        """
        canonical = json.dumps(
            {
                "adapter_version": adapter_version,
                "model_id": model_id,
                "params": params,
                "messages": messages,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def call(
        self,
        messages: list[dict[str, Any]],
        params: dict[str, Any],
        schema_id: str,
        clock: Clock,
    ) -> tuple[str, LLMRecord]:
        """Look up a recording by request_hash and replay it.

        In test mode, this NEVER makes a live network call (G2.10).
        If no recording is found, raises ReplayMissError.
        """
        request_hash = self.compute_request_hash(
            self._adapter_version,
            self._model_id,
            params,
            messages,
        )

        record = self._recordings.get(request_hash)
        if record is None:
            raise ReplayMissError(
                f"No recording found for request_hash={request_hash} "
                f"(model_id={self._model_id}, "
                f"adapter_version={self._adapter_version}). "
                f"Live network calls are disabled in test mode (G2.10)."
            )

        # Verify response_hash matches the stored response
        expected_response_hash = hashlib.sha256(
            record.response.encode("utf-8")
        ).hexdigest()
        if record.response_hash != expected_response_hash:
            raise ReplayMissError(
                f"Recording response_hash mismatch for "
                f"request_hash={request_hash}"
            )

        return record.response, record

    def add_recording(
        self,
        messages: list[dict[str, Any]],
        params: dict[str, Any],
        schema_id: str,
        response: str,
        tokens_input: int,
        tokens_output: int,
        clock: Clock,
    ) -> LLMRecord:
        """Create and store a recording (for test setup)."""
        request_hash = self.compute_request_hash(
            self._adapter_version,
            self._model_id,
            params,
            messages,
        )
        response_hash = hashlib.sha256(
            response.encode("utf-8")
        ).hexdigest()
        record = LLMRecord(
            record_id=str(uuid.uuid4()),
            request_hash=request_hash,
            response=response,
            response_hash=response_hash,
            model_id=self._model_id,
            adapter_version=self._adapter_version,
            expected_schema_id=schema_id,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            recorded_at=clock.now(),
        )
        self._recordings[request_hash] = record
        return record
