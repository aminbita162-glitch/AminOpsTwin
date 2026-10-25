#!/usr/bin/env python3
"""verify_export.py — Offline Export Bundle Verification (P19, G19.2).

Standalone script that validates a signed export bundle directory
**without importing the main application**.  Uses only stdlib
(hashlib, json, pathlib).

Usage::

    python3 scripts/verify_export.py <export_dir>
    python3 scripts/verify_export.py <export_dir> --manifest <manifest.json>

An export directory contains:
    manifest.json   — export manifest with file hashes
    <files>         — the exported files referenced by the manifest
    bundle.json     — optional bundle metadata with signature + co-signature

The script:
1. Reads ``manifest.json`` (or ``<export_dir>/manifest.json``) which
   contains a ``files`` list of {path, sha256} pairs.
2. Verifies every file in the manifest exists and its SHA-256 matches.
3. Reads ``bundle.json`` if present and validates:
   - ``signature_status`` is "signed" or "unsigned";
   - if "signed", ``signature_hash`` is a valid 64-char hex string;
   - ``co_signature_hash`` if present is a valid 64-char hex string.
4. Exits 0 on success, 1 on any failure.

This is the offline verify tool required by P19 deliverable 3.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_HEX_CHARSET = frozenset("0123456789abcdef")


def _compute_sha256(path: Path) -> str:
    """Compute SHA-256 hex of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_valid_hex64(value: Any) -> bool:
    """Return True if *value* is a 64-char lowercase hex string."""
    if not isinstance(value, str):
        return False
    if len(value) != 64:
        return False
    return all(c in _HEX_CHARSET for c in value)


def verify_export(
    export_dir: Path,
    manifest_path: Path | None = None,
) -> tuple[bool, list[str]]:
    """Verify an export bundle directory.

    Returns (success, messages).
    """
    messages: list[str] = []

    if manifest_path is None:
        manifest_path = export_dir / "manifest.json"

    if not manifest_path.exists():
        messages.append(f"FAIL: manifest not found: {manifest_path}")
        return False, messages

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        messages.append(f"FAIL: manifest read error: {exc}")
        return False, messages

    if not isinstance(manifest, dict):
        messages.append("FAIL: manifest must be a JSON object")
        return False, messages

    # Verify files in the manifest.
    files = manifest.get("entries", manifest.get("files", []))
    if not isinstance(files, list):
        messages.append("FAIL: manifest 'entries'/'files' must be a list")
        return False, messages

    file_count = 0
    for entry in files:
        if not isinstance(entry, dict):
            messages.append(f"FAIL: manifest entry not a dict: {entry}")
            continue
        file_name = entry.get("path", entry.get("file_name", ""))
        expected_hash = entry.get("sha256", entry.get("hash", ""))
        if not file_name or not expected_hash:
            messages.append(f"FAIL: manifest entry missing path/hash: {entry}")
            continue
        file_path = export_dir / file_name
        if not file_path.exists():
            messages.append(f"FAIL: file missing: {file_name}")
            continue
        actual_hash = _compute_sha256(file_path)
        file_count += 1
        if actual_hash != expected_hash:
            messages.append(
                f"FAIL: hash mismatch for {file_name}: "
                f"expected {expected_hash[:16]}… actual {actual_hash[:16]}…"
            )
        else:
            messages.append(f"PASS: {file_name}")

    # Verify bundle.json if present (signature + co-signature).
    bundle_path = export_dir / "bundle.json"
    if bundle_path.exists():
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            messages.append(f"FAIL: bundle.json read error: {exc}")
            return False, messages
        if not isinstance(bundle, dict):
            messages.append("FAIL: bundle.json must be a JSON object")
            return False, messages

        sig_status = bundle.get("signature_status", "unsigned")
        if sig_status not in ("signed", "unsigned"):
            messages.append(
                f"FAIL: invalid signature_status: {sig_status}"
            )
        elif sig_status == "signed":
            sig_hash = bundle.get("signature_hash")
            if not _is_valid_hex64(sig_hash):
                messages.append(
                    "FAIL: signature_hash must be a 64-char hex string"
                )
            else:
                messages.append("PASS: signature_hash valid")

        co_sig = bundle.get("co_signature_hash")
        if co_sig is not None:
            if not _is_valid_hex64(co_sig):
                messages.append(
                    "FAIL: co_signature_hash must be a 64-char hex string"
                )
            else:
                messages.append("PASS: co_signature_hash valid")
    else:
        messages.append("PASS: no bundle.json (unsigned export)")

    failures = [m for m in messages if m.startswith("FAIL:")]
    success = len(failures) == 0
    if success:
        messages.append(
            f"PASS: export verified — {file_count} files, 0 failures"
        )
    return success, messages


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="verify_export.py",
        description="Offline export bundle verification (P19, G19.2).",
    )
    parser.add_argument(
        "export_dir",
        type=str,
        help="Path to the export bundle directory.",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default=None,
        help="Path to manifest.json (default: <export_dir>/manifest.json).",
    )
    args = parser.parse_args()

    export_dir = Path(args.export_dir)
    manifest_path = Path(args.manifest) if args.manifest else None

    if not export_dir.exists():
        print(f"ERROR: export directory not found: {export_dir}", file=sys.stderr)
        return 1

    success, messages = verify_export(export_dir, manifest_path)
    for msg in messages:
        print(msg)
    if success:
        print("\n=== EXPORT VERIFIED ===")
        return 0
    failures = [m for m in messages if m.startswith("FAIL:")]
    print(f"\n=== EXPORT INVALID: {len(failures)} failures ===", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
