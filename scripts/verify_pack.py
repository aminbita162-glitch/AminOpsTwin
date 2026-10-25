#!/usr/bin/env python3
"""verify_pack.py — Offline Evidence Pack Verification Kit (P17, G17.4).

Standalone script that validates an evidence pack directory **without
importing the main application**.  It uses only stdlib (hashlib, json,
pathlib) and PyYAML.

Usage::

    python3 scripts/verify_pack.py <pack_dir> [--manifest <manifest.json>]
    python3 scripts/verify_pack.py <pack_dir>  # reads pack_dir/manifest.json

The script:
1. Reads ``manifest.json`` (or ``<pack_dir>/manifest.json``) which
   contains a ``files`` list of {file_name, sha256} pairs and an
   optional ``merkle_root``.
2. Verifies every file in the manifest exists and its SHA-256 matches.
3. If ``merkle_root`` is present, rebuilds the Merkle tree and checks
   the root.
4. Exits 0 on success, 1 on any failure.

This is the offline verification kit required by P17 deliverable 5.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    """Hash two hex strings (interior Merkle node)."""
    return hashlib.sha256((left + right).encode("utf-8")).hexdigest()


def _build_merkle_root(hashes: list[str]) -> str:
    """Build a Merkle root from a list of leaf hashes."""
    if not hashes:
        return hashlib.sha256(b"").hexdigest()
    level = list(hashes)
    while len(level) > 1:
        next_level: list[str] = []
        i = 0
        while i < len(level):
            left = level[i]
            if i + 1 < len(level):
                right = level[i + 1]
                next_level.append(_hash_pair(left, right))
                i += 2
            else:
                next_level.append(_hash_pair(left, left))
                i += 1
        level = next_level
    return level[0]


def verify_pack(
    pack_dir: Path,
    manifest_path: Path | None = None,
) -> tuple[bool, list[str]]:
    """Verify an evidence pack.

    Returns (success, messages).
    """
    messages: list[str] = []

    if manifest_path is None:
        manifest_path = pack_dir / "manifest.json"

    if not manifest_path.exists():
        messages.append(f"manifest not found: {manifest_path}")
        return False, messages

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        messages.append(f"manifest read error: {exc}")
        return False, messages

    if not isinstance(manifest, dict):
        messages.append("manifest must be a JSON object")
        return False, messages

    files = manifest.get("files", [])
    if not isinstance(files, list):
        messages.append("manifest 'files' must be a list")
        return False, messages

    # Verify each file.
    all_hashes: list[str] = []
    for entry in files:
        if not isinstance(entry, dict):
            messages.append(f"manifest entry not a dict: {entry}")
            continue
        file_name = entry.get("file_name", "")
        expected_hash = entry.get("sha256") or entry.get("hash") or ""

        file_path = pack_dir / file_name
        if not file_path.exists():
            messages.append(f"FAIL: file missing: {file_name}")
            continue

        actual_hash = _compute_sha256(file_path)
        all_hashes.append(actual_hash)

        if expected_hash and actual_hash != expected_hash:
            messages.append(
                f"FAIL: hash mismatch for {file_name}: "
                f"expected {expected_hash[:16]}… actual {actual_hash[:16]}…"
            )
        else:
            messages.append(f"PASS: {file_name}")

    # Verify Merkle root if present.
    merkle_root = manifest.get("merkle_root")
    if merkle_root:
        if not all_hashes:
            messages.append("FAIL: merkle_root present but no files hashed")
        else:
            computed_root = _build_merkle_root(all_hashes)
            if computed_root != merkle_root:
                messages.append(
                    f"FAIL: merkle root mismatch: "
                    f"expected {merkle_root[:16]}… "
                    f"actual {computed_root[:16]}…"
                )
            else:
                messages.append("PASS: merkle root verified")

    # Check for tampering: any FAIL message means the pack is invalid.
    failures = [m for m in messages if m.startswith("FAIL:")]
    success = len(failures) == 0
    return success, messages


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="verify_pack.py",
        description="Offline evidence pack verification kit (P17, G17.4).",
    )
    parser.add_argument(
        "pack_dir",
        type=str,
        help="Path to the evidence pack directory.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to manifest.json (default: <pack_dir>/manifest.json).",
    )
    args = parser.parse_args()

    pack_dir = Path(args.pack_dir)
    manifest_path = Path(args.manifest) if args.manifest else None

    if not pack_dir.exists():
        print(f"ERROR: pack directory not found: {pack_dir}", file=sys.stderr)
        return 1

    success, messages = verify_pack(pack_dir, manifest_path)
    for msg in messages:
        print(msg)
    if success:
        print(f"\n=== PACK VERIFIED: {len(messages)} checks passed ===")
        return 0
    else:
        failures = [m for m in messages if m.startswith("FAIL:")]
        print(f"\n=== PACK INVALID: {len(failures)} failures ===", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
