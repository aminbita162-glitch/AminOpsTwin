"""Public Prior Pack loader (Idea S2, P13, G13.3).

Loads a versioned, signed Capability Pack of aggregate prior
distributions derived from public ClinicalTrials.gov / AACT aggregate
data.  The pack is loaded read-only; its hash is recomputed at load
time and compared against the manifest's recorded hash.

No private data is included — only aggregate statistics.  The pack
is labelled SYNTHETIC until owner-approved real data is ingested via
the shadow gateway.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = [
    "PriorPackError",
    "PublicPriorPack",
    "load_public_prior_pack_v1",
]

_PACK_PATH = (
    Path(__file__).parent / "public_prior_pack_v1.json"
)


class PriorPackError(Exception):
    """Raised when the prior pack fails to load or verify."""


class PublicPriorPack:
    """A loaded public prior pack with manifest verification."""

    def __init__(self, data: dict[str, Any], pack_path: Path) -> None:
        self._data = data
        self._path = pack_path
        self._aggregate: dict[str, Any] = data.get("aggregate_statistics", {})
        self._manifest: dict[str, Any] = data.get("manifest", {})
        self._pack_id: str = data.get("pack_id", "")
        self._pack_version: str = data.get("pack_version", "")
        self._data_label: str = data.get("data_label", "")
        self._source_refs: list[dict[str, Any]] = data.get(
            "source_references", []
        )

    @property
    def pack_id(self) -> str:
        return self._pack_id

    @property
    def pack_version(self) -> str:
        return self._pack_version

    @property
    def data_label(self) -> str:
        return self._data_label

    @property
    def is_synthetic(self) -> bool:
        return self._data_label == "SYNTHETIC"

    @property
    def aggregate_statistics(self) -> dict[str, Any]:
        return self._aggregate

    @property
    def manifest(self) -> dict[str, Any]:
        return self._manifest

    @property
    def manifest_hash(self) -> str:
        return str(self._manifest.get("pack_hash", ""))

    @property
    def source_references(self) -> list[dict[str, Any]]:
        return self._source_refs

    def compute_pack_hash(self) -> str:
        """Recompute the SHA-256 hash of the aggregate_statistics."""
        import hashlib

        canonical = json.dumps(
            self._aggregate,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def verify(self) -> bool:
        """Verify that the manifest hash matches the computed hash."""
        actual = self.compute_pack_hash()
        expected = self.manifest_hash
        if expected == "PLACEHOLDER" or not expected:
            raise PriorPackError(
                "manifest pack_hash is PLACEHOLDER or empty"
            )
        return actual == expected


def load_public_prior_pack_v1(
    path: Path | None = None,
) -> PublicPriorPack:
    """Load the public_prior_pack_v1.json and verify its manifest.

    Raises PriorPackError if the file is missing, invalid, or the
    manifest hash does not match.
    """
    pack_path = path or _PACK_PATH
    if not pack_path.exists():
        raise PriorPackError(f"prior pack not found: {pack_path}")
    try:
        data = json.loads(pack_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise PriorPackError(f"failed to load prior pack: {exc}") from exc
    pack = PublicPriorPack(data, pack_path)
    if not pack.verify():
        raise PriorPackError(
            "manifest hash mismatch: "
            f"expected={pack.manifest_hash}, "
            f"actual={pack.compute_pack_hash()}"
        )
    return pack
