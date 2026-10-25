"""Evidence package — source rights, ingestion, registry with cache binding (P4).

Source rights and provenance (§30, G4.2): SourceRegistry with lifecycle.
Ingestion security (§30.4, G4.3): SourceIngestor with injection guards.
Evidence registry (§3.10, G2.4): EvidenceRegistry with cache binding.

P17 additions:
- Claim graph (G17.1): depends_on, stale-claim detection.
- Merkle evidence pack (G17.2): Merkle tree, partial proofs.
- Audit hash-chain (G17.3): prev_hash / record_hash, tamper detection.
- Temporal versioning (G17.3): append-only claim history.
"""

from aminopstwin.evidence.audit_chain import (
    AuditChain,
    AuditChainError,
    AuditRecord,
    canonical_record_bytes,
    compute_record_hash,
    verify_chain,
)
from aminopstwin.evidence.claim_graph import (
    ClaimGraph,
    ClaimRecord,
    StaleClaimError,
    compute_file_hash,
    load_claims_yaml,
    load_default_graph,
)
from aminopstwin.evidence.impact import (
    ChangeType,
    DependencyEdge,
    DependencyGraph,
    ImpactError,
    ImpactEvent,
    ImpactTracker,
)
from aminopstwin.evidence.ingestion import (
    IngestionOutcome,
    IngestionResult,
    SourceIngestor,
)
from aminopstwin.evidence.merkle_pack import (
    MerkleLeaf,
    MerkleNode,
    MerkleProof,
    MerkleProofError,
    MerkleProofStep,
    MerkleTree,
    build_merkle_tree,
    build_tree_from_directory,
    compute_file_sha256,
    generate_partial_proof,
    proof_from_dict,
    proof_to_dict,
    tree_to_dict,
    verify_partial_proof,
)
from aminopstwin.evidence.registry import (
    EvidenceEntry,
    EvidenceKey,
    EvidenceRegistry,
)
from aminopstwin.evidence.source_rights import (
    SourceRecord,
    SourceRegistry,
    SourceRegistryError,
    SourceStatus,
)
from aminopstwin.evidence.temporal_versioning import (
    ClaimHistory,
    ClaimVersion,
    TemporalRegistry,
    TemporalRegistryError,
)

__all__ = [
    # source rights
    "SourceStatus",
    "SourceRecord",
    "SourceRegistry",
    "SourceRegistryError",
    # ingestion
    "SourceIngestor",
    "IngestionResult",
    "IngestionOutcome",
    # evidence registry
    "EvidenceKey",
    "EvidenceEntry",
    "EvidenceRegistry",
    # impact tracking (P5)
    "ChangeType",
    "DependencyEdge",
    "DependencyGraph",
    "ImpactEvent",
    "ImpactTracker",
    "ImpactError",
    # claim graph (P17, G17.1)
    "ClaimGraph",
    "ClaimRecord",
    "StaleClaimError",
    "load_claims_yaml",
    "load_default_graph",
    "compute_file_hash",
    # merkle pack (P17, G17.2)
    "MerkleLeaf",
    "MerkleNode",
    "MerkleTree",
    "MerkleProof",
    "MerkleProofStep",
    "MerkleProofError",
    "build_merkle_tree",
    "build_tree_from_directory",
    "generate_partial_proof",
    "verify_partial_proof",
    "compute_file_sha256",
    "proof_to_dict",
    "proof_from_dict",
    "tree_to_dict",
    # audit chain (P17, G17.3)
    "AuditRecord",
    "AuditChain",
    "AuditChainError",
    "canonical_record_bytes",
    "compute_record_hash",
    "verify_chain",
    # temporal versioning (P17, G17.3)
    "ClaimVersion",
    "ClaimHistory",
    "TemporalRegistry",
    "TemporalRegistryError",
]
