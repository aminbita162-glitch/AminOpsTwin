"""Signed export bundles with owner-side signing (§38 operational rule 7).

Export preparation produces UNSIGNED bundles; the signing key is never
held by the agent. The owner provides a 64-char hex signature hash to
produce a SIGNED bundle. No cryptographic signing library is imported —
signing is simulated by the owner supplying a hash (§38 rule 7).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from aminopstwin.enterprise.manifest import (
    ExportManifest,
    build_manifest,
)

__all__ = [
    "ExportSignatureStatus",
    "ExportBundle",
    "ExportSignatureError",
    "build_export_bundle",
    "verify_bundle",
    "sign_bundle",
    "NO_AGENT_HELD_KEY",
]


#: The agent holds no private signing key (§38 rule 7). Signing is
#: performed out-of-band by the owner, who supplies a signature hash.
NO_AGENT_HELD_KEY: bool = True


class ExportSignatureError(Exception):
    """Raised when an export bundle's signature is missing or invalid."""


class ExportSignatureStatus(StrEnum):
    """Signature status of an export bundle (§38 rule 7)."""

    UNSIGNED = "unsigned"
    SIGNED = "signed"


@dataclass(frozen=True)
class ExportBundle:
    """A signed or unsigned export bundle (§38 rule 7).

    Bundles are UNSIGNED by default. The owner signs out-of-band by
    providing a 64-char hex ``signature_hash`` via :func:`sign_bundle`.
    No agent-held key is involved (see :data:`NO_AGENT_HELD_KEY`).
    """

    bundle_id: str
    manifest: ExportManifest
    created_at: str
    bundle_hash: str
    signature_status: ExportSignatureStatus = ExportSignatureStatus.UNSIGNED
    signature_hash: str | None = None


def build_export_bundle(
    base_path: Path,
    patterns: list[str] | None = None,
) -> ExportBundle:
    """Build an UNSIGNED export bundle from files under ``base_path``.

    The ``bundle_hash`` is the SHA-256 of the manifest's canonical JSON
    (``manifest.to_json()``). The bundle is UNSIGNED by default — per
    §38 rule 7, signing is the owner's responsibility.
    """
    manifest = build_manifest(base_path, patterns)
    bundle_hash = hashlib.sha256(manifest.to_json().encode("utf-8")).hexdigest()
    bundle_id = str(uuid.uuid4())
    created_at = datetime.now(tz=UTC).isoformat()
    return ExportBundle(
        bundle_id=bundle_id,
        manifest=manifest,
        created_at=created_at,
        bundle_hash=bundle_hash,
        signature_status=ExportSignatureStatus.UNSIGNED,
        signature_hash=None,
    )


def verify_bundle(bundle: ExportBundle, base_path: Path) -> int:
    """Verify an export bundle's manifest files and signature status.

    Returns the number of manifest files verified. Raises
    :class:`ExportSignatureError` if the bundle is signed but its
    signature hash is not a valid 64-char hex string. Raises
    :class:`ManifestError` (via the manifest) if any file on disk
    does not match its manifest hash.
    """
    if bundle.signature_status == ExportSignatureStatus.SIGNED:
        sig = bundle.signature_hash
        if sig is None:
            raise ExportSignatureError(
                "SIGNED bundle is missing its signature_hash"
            )
        if len(sig) != 64:
            raise ExportSignatureError(
                f"SIGNED bundle signature_hash must be 64 chars, "
                f"got {len(sig)}"
            )
        if not all(c in "0123456789abcdef" for c in sig):
            raise ExportSignatureError(
                "SIGNED bundle signature_hash must be a hex string"
            )
    return bundle.manifest.verify_files(base_path)


def sign_bundle(
    bundle: ExportBundle,
    owner_signature_hash: str,
) -> ExportBundle:
    """Return a new SIGNED bundle carrying the owner-supplied signature hash.

    The agent holds no signing key (§38 rule 7); the owner supplies a
    64-char hex ``owner_signature_hash`` out-of-band. Raises
    :class:`ExportSignatureError` if the hash is not a valid 64-char
    hex string.
    """
    if len(owner_signature_hash) != 64:
        raise ExportSignatureError(
            "owner_signature_hash must be a 64-char hex string, "
            f"got length {len(owner_signature_hash)}"
        )
    if not all(c in "0123456789abcdef" for c in owner_signature_hash):
        raise ExportSignatureError(
            "owner_signature_hash must be a hex string (0-9, a-f)"
        )
    return ExportBundle(
        bundle_id=bundle.bundle_id,
        manifest=bundle.manifest,
        created_at=bundle.created_at,
        bundle_hash=bundle.bundle_hash,
        signature_status=ExportSignatureStatus.SIGNED,
        signature_hash=owner_signature_hash,
    )
