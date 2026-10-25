"""Temporal Versioning — append-only claim history (P17, G17.3).

Stores the history of claim hash values over time.  Each version of a
claim is recorded as a ``ClaimVersion`` entry.  Previous hashes remain
queryable after an update, so the history is append-only.

This module uses only stdlib (hashlib, json) — no main application
imports — so it can be used by the offline verification kit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "ClaimVersion",
    "ClaimHistory",
    "TemporalRegistry",
    "TemporalRegistryError",
]


@dataclass(frozen=True)
class ClaimVersion:
    """A single version of a claim.

    Attributes
    ----------
    claim_id:
        The claim ID (e.g. "CLAIM-001").
    version:
        Monotonic version number (1-based).
    hash:
        The SHA-256 hex of the evidence file at this version.
    recorded_at:
        Integer timestamp (deterministic — from injected clock).
    evidence_path:
        The evidence file path.
    """

    claim_id: str
    version: int
    hash: str
    recorded_at: int
    evidence_path: str


@dataclass
class ClaimHistory:
    """Append-only history for a single claim.

    Attributes
    ----------
    claim_id:
        The claim ID.
    versions:
        Ordered list of ClaimVersion entries (oldest first).
    """

    claim_id: str
    versions: list[ClaimVersion] = field(default_factory=list)

    @property
    def current(self) -> ClaimVersion | None:
        """The latest version (or None if empty)."""
        return self.versions[-1] if self.versions else None

    @property
    def current_hash(self) -> str | None:
        """The latest hash (or None if empty)."""
        return self.current.hash if self.current else None

    def add_version(
        self,
        hash_val: str,
        recorded_at: int,
        evidence_path: str,
    ) -> ClaimVersion:
        """Append a new version and return it."""
        version_num = len(self.versions) + 1
        cv = ClaimVersion(
            claim_id=self.claim_id,
            version=version_num,
            hash=hash_val,
            recorded_at=recorded_at,
            evidence_path=evidence_path,
        )
        self.versions.append(cv)
        return cv

    def get_version(self, version: int) -> ClaimVersion | None:
        """Return the ClaimVersion for ``version`` (1-based), or None."""
        if 1 <= version <= len(self.versions):
            return self.versions[version - 1]
        return None

    def get_hash_at_version(self, version: int) -> str | None:
        """Return the hash at ``version`` (1-based), or None."""
        cv = self.get_version(version)
        return cv.hash if cv else None

    def prior_hash(self) -> str | None:
        """Return the second-to-last hash (the previous version's hash).

        Returns None if there are fewer than 2 versions.
        """
        if len(self.versions) < 2:
            return None
        return self.versions[-2].hash

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-serializable dict."""
        return {
            "claim_id": self.claim_id,
            "versions": [
                {
                    "version": v.version,
                    "hash": v.hash,
                    "recorded_at": v.recorded_at,
                    "evidence_path": v.evidence_path,
                }
                for v in self.versions
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ClaimHistory:
        """Deserialize from a dict."""
        history = cls(claim_id=data["claim_id"])
        for v in data.get("versions", []):
            history.versions.append(ClaimVersion(
                claim_id=data["claim_id"],
                version=v["version"],
                hash=v["hash"],
                recorded_at=v["recorded_at"],
                evidence_path=v["evidence_path"],
            ))
        return history


class TemporalRegistryError(Exception):
    """Raised on temporal registry errors."""


class TemporalRegistry:
    """Append-only temporal versioning for all claims.

    Stores a ClaimHistory per claim_id.  After an update, the prior
    hash remains retrievable via ``get_prior_hash(claim_id)`` or
    ``get_hash_at_version(claim_id, version)``.
    """

    def __init__(self) -> None:
        self._histories: dict[str, ClaimHistory] = {}

    def record(
        self,
        claim_id: str,
        hash_val: str,
        recorded_at: int,
        evidence_path: str,
    ) -> ClaimVersion:
        """Record a new version of ``claim_id`` and return it."""
        if claim_id not in self._histories:
            self._histories[claim_id] = ClaimHistory(claim_id=claim_id)
        return self._histories[claim_id].add_version(
            hash_val, recorded_at, evidence_path,
        )

    def get_history(self, claim_id: str) -> ClaimHistory | None:
        """Return the full history for ``claim_id``, or None."""
        return self._histories.get(claim_id)

    def get_prior_hash(self, claim_id: str) -> str | None:
        """Return the prior (second-to-last) hash for ``claim_id``."""
        history = self._histories.get(claim_id)
        if history is None:
            return None
        return history.prior_hash()

    def get_hash_at_version(
        self,
        claim_id: str,
        version: int,
    ) -> str | None:
        """Return the hash at ``version`` for ``claim_id``."""
        history = self._histories.get(claim_id)
        if history is None:
            return None
        return history.get_hash_at_version(version)

    def get_current_hash(self, claim_id: str) -> str | None:
        """Return the current (latest) hash for ``claim_id``."""
        history = self._histories.get(claim_id)
        if history is None:
            return None
        return history.current_hash

    @property
    def claim_ids(self) -> list[str]:
        """All claim IDs with recorded history."""
        return sorted(self._histories.keys())

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire registry to a JSON-serializable dict."""
        return {
            cid: hist.to_dict()
            for cid, hist in sorted(self._histories.items())
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TemporalRegistry:
        """Deserialize from a dict."""
        registry = cls()
        for cid, hist_data in data.items():
            registry._histories[cid] = ClaimHistory.from_dict(hist_data)
        return registry

    def save(self, path: str | object) -> None:
        """Save the registry to a JSON file."""
        p = Path(path)  # type: ignore[arg-type]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | object) -> TemporalRegistry:
        """Load the registry from a JSON file."""
        p = Path(path)  # type: ignore[arg-type]
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_dict(data)
