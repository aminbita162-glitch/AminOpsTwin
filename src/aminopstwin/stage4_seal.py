"""Stage 4 Seal — signed document with git tree hash and claim-ids (P24).

The Stage 4 Seal is a signed document containing:

1. The git tree hash of HEAD at the Stage 4 close.
2. The list of active claim-ids from ``docs/claims.yaml``.
3. An HMAC-SHA256 signature over the (tree_hash, claim_ids) pair
   using a provided signing key.

The seal is written to ``docs/stage4_seal.json`` and can be verified
by :func:`verify_stage4_seal`.

This is the Stage 4 counterpart of the Stage 3 Seal
(:mod:`aminopstwin.stage_seal`).  Stage 4 closes P21–P24.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
from pathlib import Path
from typing import Any

__all__ = [
    "Stage4Seal",
    "generate_stage4_seal",
    "verify_stage4_seal",
    "compute_tree_hash",
    "load_claim_ids",
    "write_stage4_seal",
]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SEAL_PATH = REPO_ROOT / "docs" / "stage4_seal.json"
CLAIMS_PATH = REPO_ROOT / "docs" / "claims.yaml"


def compute_tree_hash(repo_root: Path | None = None) -> str:
    """Compute the git tree hash of HEAD.

    Uses ``git rev-parse HEAD^{tree}`` to get the tree object hash.
    Falls back to ``git write-tree`` if rev-parse fails.
    """
    root = repo_root or REPO_ROOT
    result = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    # Fallback: write-tree
    result = subprocess.run(
        ["git", "write-tree"],
        capture_output=True,
        text=True,
        cwd=str(root),
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    raise RuntimeError(f"Failed to compute git tree hash: {result.stderr}")


def load_claim_ids(claims_path: Path | None = None) -> list[str]:
    """Load the list of claim-ids from ``docs/claims.yaml``.

    Uses a simple line-based parser to avoid a yaml dependency at
    runtime — the file format is well-known and stable.
    """
    path = claims_path or CLAIMS_PATH
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    claim_ids: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- claim_id:"):
            value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
            if value:
                claim_ids.append(value)
    return claim_ids


class Stage4Seal:
    """Stage 4 Seal — signed document with tree hash and claim-ids.

    Attributes:
        stage: Stage identifier (always "4").
        tree_hash: Git tree hash of HEAD at close time.
        claim_ids: Sorted list of active claim-ids.
        signature: HMAC-SHA256 hex over (tree_hash, claim_ids).
        signing_key: The key used for signing (for re-verification).
    """

    def __init__(
        self,
        *,
        tree_hash: str,
        claim_ids: list[str],
        signature: str,
        signing_key: str,
    ) -> None:
        self.tree_hash = tree_hash
        self.claim_ids = sorted(claim_ids)
        self.signature = signature
        self.signing_key = signing_key

    @property
    def stage(self) -> str:
        return "4"

    def _message(self) -> str:
        """The canonical message that the signature covers."""
        return f"{self.tree_hash}:{','.join(self.claim_ids)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "tree_hash": self.tree_hash,
            "claim_ids": self.claim_ids,
            "signature": self.signature,
        }

    def to_json(self) -> str:
        """Serialize the seal to canonical JSON."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    def verify(self) -> bool:
        """Verify the seal's signature against its contents."""
        expected = hmac.new(
            self.signing_key.encode("utf-8"),
            self._message().encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, self.signature)


def generate_stage4_seal(
    signing_key: str,
    *,
    repo_root: Path | None = None,
    claims_path: Path | None = None,
) -> Stage4Seal:
    """Generate a Stage 4 seal with the current tree hash and claim-ids."""
    root = repo_root or REPO_ROOT
    tree_hash = compute_tree_hash(root)
    claim_ids = load_claim_ids(claims_path)
    seal = Stage4Seal(
        tree_hash=tree_hash,
        claim_ids=claim_ids,
        signature="",
        signing_key=signing_key,
    )
    signature = hmac.new(
        signing_key.encode("utf-8"),
        seal._message().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return Stage4Seal(
        tree_hash=tree_hash,
        claim_ids=claim_ids,
        signature=signature,
        signing_key=signing_key,
    )


def verify_stage4_seal(
    seal: Stage4Seal,
    *,
    expected_tree_hash: str | None = None,
    expected_claim_ids: list[str] | None = None,
) -> bool:
    """Verify a Stage 4 Seal.

    Checks:
    1. The signature is valid for the (tree_hash, claim_ids) pair.
    2. If *expected_tree_hash* is provided, it matches.
    3. If *expected_claim_ids* are provided, they match.

    Returns True only if all checks pass.
    """
    if not seal.verify():
        return False
    if expected_tree_hash is not None and seal.tree_hash != expected_tree_hash:
        return False
    if expected_claim_ids is not None:
        expected = sorted(expected_claim_ids)
        if sorted(seal.claim_ids) != expected:
            return False
    return True


def write_stage4_seal(
    seal: Stage4Seal,
    output_path: Path | None = None,
) -> Path:
    """Write the seal to ``docs/stage4_seal.json`` (or *output_path*)."""
    path = output_path or SEAL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(seal.to_json(), encoding="utf-8")
    return path
