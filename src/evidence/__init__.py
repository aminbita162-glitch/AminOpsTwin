"""Evidence package — registry with cache binding (§3.10, G2.4).

The Evidence Registry stores evidence entries keyed by a cryptographic
outer key. Cache binding detects tampering with source_hash, claim_span,
policy_epoch, or retrieval_window after storage (G2.4, GW-EVID-001).
"""

from src.evidence.registry import (
    EvidenceEntry,
    EvidenceKey,
    EvidenceRegistry,
)

__all__ = ["EvidenceKey", "EvidenceEntry", "EvidenceRegistry"]
