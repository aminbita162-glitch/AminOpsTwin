"""Claim Graph — dependency tracking and stale-claim detection (P17, G17.1).

Extends the Evidence Claim Registry (docs/claims.yaml) with an optional
``depends_on`` list per claim.  A claim is *stale* when its evidence_path
hash no longer matches the recorded hash AND the claim has not been
updated in the current tree — i.e., the evidence changed but the claim
was not refreshed.

The ClaimGraph loads claims.yaml, builds a directed dependency graph,
and provides:

* ``detect_stale_claims()`` — returns the list of claims whose
  evidence file hash does not match the recorded hash.
* ``verify_graph()`` — returns True iff every claim is fresh AND every
  ``depends_on`` target exists.
* ``topological_sort()`` — returns claim IDs in dependency order.

This module is importable without the main application — it uses only
stdlib (hashlib, json, pathlib) and PyYAML.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment, unused-ignore]

__all__ = [
    "ClaimRecord",
    "ClaimGraph",
    "StaleClaimError",
    "load_claims_yaml",
    "compute_file_hash",
]


def compute_file_hash(path: Path) -> str:
    """Compute SHA-256 hex of a file or directory.

    For a directory, the hash is over the sorted concatenation of all
    file contents (with path separators) — matching the existing
    ``aminopstwin-verify`` compute_file_hash semantics.
    """
    hasher = hashlib.sha256()
    if path.is_dir():
        for fpath in sorted(path.rglob("*")):
            if fpath.is_file():
                rel = fpath.relative_to(path)
                hasher.update(rel.as_posix().encode("utf-8"))
                hasher.update(b"\0")
                hasher.update(fpath.read_bytes())
    elif path.is_file():
        hasher.update(path.read_bytes())
    else:
        raise FileNotFoundError(f"evidence path not found: {path}")
    return hasher.hexdigest()


@dataclass(frozen=True)
class ClaimRecord:
    """A single claim parsed from claims.yaml."""

    claim_id: str
    text: str
    evidence_path: str
    hash: str
    category: str
    depends_on: list[str] = field(default_factory=list)


class StaleClaimError(Exception):
    """Raised when one or more claims are stale (evidence hash mismatch)."""

    def __init__(self, stale: list[tuple[str, str, str, str]]) -> None:
        self.stale = stale
        lines = [f"  {cid}: expected {exp[:16]}… actual {act[:16]}… ({ep})"
                 for cid, ep, exp, act in stale]
        super().__init__("Stale claims detected:\n" + "\n".join(lines))


def load_claims_yaml(claims_path: Path) -> list[ClaimRecord]:
    """Load and parse claims.yaml into ClaimRecord objects."""
    if yaml is None:
        raise ImportError("PyYAML is required to load claims.yaml")
    with claims_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "claims" not in data:
        raise ValueError(f"invalid claims format in {claims_path}")
    records: list[ClaimRecord] = []
    for entry in data["claims"]:
        records.append(ClaimRecord(
            claim_id=entry["claim_id"],
            text=entry.get("text", ""),
            evidence_path=entry["evidence_path"],
            hash=entry["hash"],
            category=entry.get("category", ""),
            depends_on=entry.get("depends_on", []) or [],
        ))
    return records


class ClaimGraph:
    """Directed dependency graph over claims with stale-claim detection.

    Parameters
    ----------
    claims:
        List of ClaimRecord objects (typically from ``load_claims_yaml``).
    repo_root:
        Repository root for resolving evidence_path values.
    """

    def __init__(
        self,
        claims: list[ClaimRecord],
        repo_root: Path,
    ) -> None:
        self._claims = claims
        self._repo_root = repo_root
        self._by_id: dict[str, ClaimRecord] = {c.claim_id: c for c in claims}

    # ------------------------------------------------------------------
    # Stale-claim detection
    # ------------------------------------------------------------------

    def detect_stale_claims(self) -> list[tuple[str, str, str, str]]:
        """Return list of (claim_id, evidence_path, expected, actual) for stale claims.

        A claim is stale when its evidence_path hash does not match the
        recorded hash.  Claims with hash ``"PLACEHOLDER"`` are always
        considered stale.
        """
        stale: list[tuple[str, str, str, str]] = []
        for claim in self._claims:
            evidence_path = self._repo_root / claim.evidence_path
            if not evidence_path.exists():
                stale.append((
                    claim.claim_id,
                    claim.evidence_path,
                    claim.hash,
                    "FILE_NOT_FOUND",
                ))
                continue
            if claim.hash == "PLACEHOLDER":
                stale.append((
                    claim.claim_id,
                    claim.evidence_path,
                    claim.hash,
                    "PLACEHOLDER_NOT_COMPUTED",
                ))
                continue
            actual = compute_file_hash(evidence_path)
            if actual != claim.hash:
                stale.append((
                    claim.claim_id,
                    claim.evidence_path,
                    claim.hash,
                    actual,
                ))
        return stale

    def verify_graph(self) -> bool:
        """Return True iff no stale claims and every depends_on target exists."""
        stale = self.detect_stale_claims()
        if stale:
            return False
        for claim in self._claims:
            for dep in claim.depends_on:
                if dep not in self._by_id:
                    return False
        return True

    def missing_dependencies(self) -> list[tuple[str, str]]:
        """Return list of (claim_id, missing_dep_id) for missing depends_on targets."""
        missing: list[tuple[str, str]] = []
        for claim in self._claims:
            for dep in claim.depends_on:
                if dep not in self._by_id:
                    missing.append((claim.claim_id, dep))
        return missing

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def topological_sort(self) -> list[str]:
        """Return claim IDs in topological order (dependencies first).

        Raises ``ValueError`` if the dependency graph has a cycle.
        """
        visited: set[str] = set()
        in_progress: set[str] = set()
        order: list[str] = []

        def visit(cid: str) -> None:
            if cid in visited:
                return
            if cid in in_progress:
                raise ValueError(f"cycle in claim dependency graph at {cid}")
            in_progress.add(cid)
            claim = self._by_id.get(cid)
            if claim:
                for dep in claim.depends_on:
                    if dep in self._by_id:
                        visit(dep)
            in_progress.discard(cid)
            visited.add(cid)
            order.append(cid)

        for claim in self._claims:
            visit(claim.claim_id)
        return order

    def dependents_of(self, claim_id: str) -> list[str]:
        """Return list of claim IDs that depend on ``claim_id``."""
        return [
            c.claim_id for c in self._claims
            if claim_id in c.depends_on
        ]

    def dependencies_of(self, claim_id: str) -> list[str]:
        """Return the depends_on list for ``claim_id`` (empty if not found)."""
        claim = self._by_id.get(claim_id)
        return list(claim.depends_on) if claim else []

    @property
    def claims(self) -> list[ClaimRecord]:
        """All claim records."""
        return list(self._claims)

    def get(self, claim_id: str) -> ClaimRecord | None:
        """Return the ClaimRecord for ``claim_id`` or None."""
        return self._by_id.get(claim_id)


# ------------------------------------------------------------------
# Convenience: load from the default repo location
# ------------------------------------------------------------------


def load_default_graph(repo_root: Path) -> ClaimGraph:
    """Load ClaimGraph from ``repo_root / docs / claims.yaml``."""
    claims = load_claims_yaml(repo_root / "docs" / "claims.yaml")
    return ClaimGraph(claims, repo_root)


def _canonical_json(obj: Any) -> str:
    """Canonical JSON for deterministic hashing."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
