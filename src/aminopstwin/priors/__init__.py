"""Public Prior Pack loader (Idea S2, P13, G13.3, G19.4).

Loads a versioned, signed Capability Pack of aggregate prior
distributions derived from public ClinicalTrials.gov / AACT aggregate
data.  The pack is loaded read-only; its hash is recomputed at load
time and compared against the manifest's recorded hash.

G19.4 adds multi-version prior support: the ``MultiVersionPriorPack``
selects a version by preference, computes the version hash, and
records it in every Evidence Pack so that the chosen prior version is
cryptographically bound to the assurance output.

No private data is included — only aggregate statistics.  The pack
is labelled SYNTHETIC until owner-approved real data is ingested via
the shadow gateway.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

__all__ = [
    "PriorPackError",
    "PriorVersion",
    "PublicPriorPack",
    "MultiVersionPriorPack",
    "load_public_prior_pack_v1",
    "load_public_prior_pack_v2",
    "load_prior_pack_by_version",
]

_PACK_V1_PATH = (
    Path(__file__).parent / "public_prior_pack_v1.json"
)
_PACK_V2_PATH = (
    Path(__file__).parent / "public_prior_pack_v2.json"
)


class PriorPackError(Exception):
    """Raised when the prior pack fails to load or verify."""


class PriorVersion(StrEnum):
    """Enumerates the available prior pack versions (G19.4)."""

    V1 = "1.0"
    V2 = "2.0"

    @property
    def numeric(self) -> int:
        """Return the numeric major version for comparison."""
        return int(self.value.split(".")[0])


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
        canonical = json.dumps(
            self._aggregate,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def compute_version_hash(self) -> str:
        """Compute the SHA-256 version hash (G19.4).

        The version hash is the SHA-256 of the canonical bytes of the
        full pack file content (pack_id, pack_version, aggregate_statistics,
        manifest).  This binds the chosen version to the Evidence Pack.
        """
        payload: dict[str, Any] = {
            "pack_id": self._pack_id,
            "pack_version": self._pack_version,
            "aggregate_statistics": self._aggregate,
            "manifest_pack_hash": self.manifest_hash,
        }
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    @property
    def version(self) -> PriorVersion:
        """Return the ``PriorVersion`` for this pack."""
        return PriorVersion(self._pack_version)

    def verify(self) -> bool:
        """Verify that the manifest hash matches the computed hash."""
        actual = self.compute_pack_hash()
        expected = self.manifest_hash
        if expected == "PLACEHOLDER" or not expected:
            raise PriorPackError(
                "manifest pack_hash is PLACEHOLDER or empty"
            )
        return actual == expected


# ---------------------------------------------------------------------
# Multi-version prior pack (G19.4)
# ---------------------------------------------------------------------


class MultiVersionPriorPack:
    """Multi-version prior pack selector (G19.4).

    Loads multiple prior pack versions and selects one by version
    preference.  The selected pack's ``version_hash`` is recorded in
    every Evidence Pack so that the chosen prior version is
    cryptographically bound to the assurance output.
    """

    def __init__(
        self,
        packs: dict[str, PublicPriorPack],
        selected_version: PriorVersion,
    ) -> None:
        if not packs:
            raise PriorPackError("no prior packs provided")
        self._packs = dict(packs)
        if selected_version.value not in self._packs:
            raise PriorPackError(
                f"selected version {selected_version.value} "
                f"not in loaded packs: {sorted(self._packs)}"
            )
        self._selected_version = selected_version
        self._selected_pack = self._packs[selected_version.value]

    @property
    def available_versions(self) -> list[str]:
        """Return the sorted list of available version strings."""
        return sorted(self._packs.keys())

    @property
    def selected_version(self) -> PriorVersion:
        return self._selected_version

    @property
    def selected_pack(self) -> PublicPriorPack:
        return self._selected_pack

    @property
    def version_hash(self) -> str:
        """The version hash of the selected pack (G19.4)."""
        return self._selected_pack.compute_version_hash()

    @property
    def pack_hash(self) -> str:
        """The aggregate pack hash of the selected pack."""
        return self._selected_pack.compute_pack_hash()

    @property
    def pack_id(self) -> str:
        return self._selected_pack.pack_id

    @property
    def pack_version(self) -> str:
        return self._selected_pack.pack_version

    @property
    def data_label(self) -> str:
        return self._selected_pack.data_label

    @property
    def is_synthetic(self) -> bool:
        return self._selected_pack.is_synthetic

    @property
    def aggregate_statistics(self) -> dict[str, Any]:
        return self._selected_pack.aggregate_statistics

    def get_pack(self, version: str) -> PublicPriorPack:
        """Return the pack for *version* or raise."""
        if version not in self._packs:
            raise PriorPackError(
                f"version {version} not available: "
                f"{sorted(self._packs)}"
            )
        return self._packs[version]

    def to_evidence_record(self) -> dict[str, Any]:
        """Return a deterministic record for embedding in Evidence Packs.

        The record contains the selected version string, the pack_id,
        and the version_hash.  This record is included in every Evidence
        Pack so that the prior version is cryptographically bound (G19.4).
        """
        return {
            "prior_version": self._selected_version.value,
            "pack_id": self._selected_pack.pack_id,
            "version_hash": self.version_hash,
        }


def _load_pack_from_path(path: Path) -> PublicPriorPack:
    """Load a prior pack from *path* and verify its manifest."""
    if not path.exists():
        raise PriorPackError(f"prior pack not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise PriorPackError(f"failed to load prior pack: {exc}") from exc
    pack = PublicPriorPack(data, path)
    if not pack.verify():
        raise PriorPackError(
            "manifest hash mismatch: "
            f"expected={pack.manifest_hash}, "
            f"actual={pack.compute_pack_hash()}"
        )
    return pack


def load_public_prior_pack_v1(
    path: Path | None = None,
) -> PublicPriorPack:
    """Load the public_prior_pack_v1.json and verify its manifest.

    Raises PriorPackError if the file is missing, invalid, or the
    manifest hash does not match.
    """
    return _load_pack_from_path(path or _PACK_V1_PATH)


def load_public_prior_pack_v2(
    path: Path | None = None,
) -> PublicPriorPack:
    """Load the public_prior_pack_v2.json and verify its manifest.

    Raises PriorPackError if the file is missing, invalid, or the
    manifest hash does not match.
    """
    return _load_pack_from_path(path or _PACK_V2_PATH)


def load_prior_pack_by_version(
    version: PriorVersion,
    *,
    v1_path: Path | None = None,
    v2_path: Path | None = None,
) -> PublicPriorPack:
    """Load the prior pack for *version* and verify its manifest (G19.4).

    Raises PriorPackError if the version is unknown or the pack
    fails to load/verify.
    """
    if version == PriorVersion.V1:
        return load_public_prior_pack_v1(v1_path)
    if version == PriorVersion.V2:
        return load_public_prior_pack_v2(v2_path)
    raise PriorPackError(f"unknown prior version: {version}")


def load_multi_version_prior_pack(
    *,
    preferred: PriorVersion = PriorVersion.V2,
    v1_path: Path | None = None,
    v2_path: Path | None = None,
) -> MultiVersionPriorPack:
    """Load all available prior packs and select *preferred* (G19.4).

    Loads both v1 and v2 packs, verifies each manifest, and returns a
    ``MultiVersionPriorPack`` with *preferred* selected.  Raises
    ``PriorPackError`` if any pack fails to load.
    """
    packs: dict[str, PublicPriorPack] = {}
    v1 = load_public_prior_pack_v1(v1_path)
    packs[v1.pack_version] = v1
    v2 = load_public_prior_pack_v2(v2_path)
    packs[v2.pack_version] = v2
    return MultiVersionPriorPack(packs, preferred)
