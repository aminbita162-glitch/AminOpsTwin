"""Export manifest with hash verification (P8, G5.3).

Builds a manifest of all exportable files with their SHA-256 hashes.
G5.3 requires 100% of files hash-verified against manifests.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "ExportManifest",
    "ManifestEntry",
    "ManifestError",
    "build_manifest",
]


class ManifestError(Exception):
    """Raised when manifest verification fails."""


@dataclass(frozen=True)
class ManifestEntry:
    """A single entry in the export manifest."""

    path: str
    sha256: str
    size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
        }


@dataclass
class ExportManifest:
    """Export manifest with hash-verified entries (G5.3).

    100% of files must hash-verify against the manifest.  Any
    mismatch raises ManifestError.
    """

    entries: list[ManifestEntry] = field(default_factory=list)
    manifest_version: str = "1.0"

    @property
    def count(self) -> int:
        return len(self.entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "count": self.count,
            "entries": [e.to_dict() for e in self.entries],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def verify(self) -> int:
        """Verify all entries' hashes are valid SHA-256.

        Returns the number of verified entries.
        Raises ManifestError if any entry has an invalid hash.
        """
        verified = 0
        for entry in self.entries:
            if len(entry.sha256) != 64:
                raise ManifestError(
                    f"Invalid hash length for {entry.path}: "
                    f"{len(entry.sha256)}"
                )
            if not all(
                c in "0123456789abcdef" for c in entry.sha256
            ):
                raise ManifestError(
                    f"Invalid hash characters for {entry.path}"
                )
            verified += 1
        return verified

    def verify_files(self, base_path: Path) -> int:
        """Verify that files on disk match their manifest hashes.

        Returns the number of verified files.
        Raises ManifestError if any file's hash does not match.
        """
        verified = 0
        for entry in self.entries:
            file_path = base_path / entry.path
            if not file_path.exists():
                raise ManifestError(
                    f"File not found: {entry.path}"
                )
            content = file_path.read_bytes()
            actual_hash = hashlib.sha256(content).hexdigest()
            if actual_hash != entry.sha256:
                raise ManifestError(
                    f"Hash mismatch for {entry.path}: "
                    f"expected {entry.sha256[:16]}..., "
                    f"got {actual_hash[:16]}..."
                )
            verified += 1
        return verified


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_manifest(
    base_path: Path,
    patterns: list[str] | None = None,
) -> ExportManifest:
    """Build an export manifest from files matching the given patterns.

    Default patterns: all .py, .json, .yaml, .md, .txt, .html files
    under the base path.
    """
    if patterns is None:
        patterns = ["*.py", "*.json", "*.yaml", "*.md", "*.txt", "*.html"]

    entries: list[ManifestEntry] = []
    seen: set[str] = set()

    for pattern in patterns:
        for file_path in sorted(base_path.rglob(pattern)):
            if file_path.is_dir():
                continue
            if "__pycache__" in str(file_path):
                continue
            if ".git" in str(file_path):
                continue
            if ".venv" in str(file_path):
                continue
            if "htmlcov" in str(file_path):
                continue
            if ".mutmut-cache" in str(file_path):
                continue
            rel = str(file_path.relative_to(base_path))
            if rel in seen:
                continue
            seen.add(rel)
            entries.append(
                ManifestEntry(
                    path=rel,
                    sha256=_sha256_file(file_path),
                    size=file_path.stat().st_size,
                )
            )

    entries.sort(key=lambda e: e.path)
    return ExportManifest(entries=entries)
