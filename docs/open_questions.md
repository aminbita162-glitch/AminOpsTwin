# open_questions.md (§6.1)
# Ambiguity protocol: if a requirement is ambiguous or two readings are plausible,
# the agent does NOT choose. It writes an entry here and HARD STOPs.

## Open Questions

### OQ-P1-001: Owner decisions OD02-OD06 not supplied
- **Id:** OQ-P1-001
- **Quote:** "OD02 Revocation semantics [OWNER-FILL] ... OD06 Authority precedence [OWNER-FILL]"
- **Interpretation A:** The owner will supply these before P2 (per §37 due boundaries).
- **Interpretation B:** These are not needed for P1 since P1 is foundation/governance.
- **Impact:** P1 does not depend on the full OD02-OD06 text; the agent proceeds with
  the summaries in §10 and the contracts in §3.5.5, §3.6, §3.7, §0.6. Resolution needed
  before P2 runtime tests that exercise revocation, UNKNOWN handling, and audit anchoring.
- **Status:** Recorded per §6.1. P1 proceeds; owner resolution required before the
  affected runtime phase (P2).

### OQ-P1-002: 60 capability definitions not supplied
- **Id:** OQ-P1-002
- **Quote:** "Supply the actual 60 capability definitions and complete OD01-OD07"
- **Impact:** §20 checklist requires /docs/capability_catalog.yaml with all 60 IDs.
  The agent creates a catalog with the 60 ID stubs; full definitions remain [OWNER-FILL].
  P1 does not block on the full definitions (they are pre-P1 checklist items the owner
  supplies), but the catalog file exists with status SPECIFIED/NOT_RUN.
- **Status:** Recorded per §6.1.

### OQ-P1-003: Budget governor default limits not supplied
- **Id:** OQ-P1-003
- **Quote:** "4.3 ADAPTIVE RUNTIME BUDGET GOVERNOR ... Default limits [OWNER-FILL]"
- **Impact:** The budget governor is a P2 deliverable (skeleton in P1). Default token
  budget limits for session/workflow/capability levels are not yet supplied by the owner.
  P1 does not require them; P2 does.
- **Status:** Recorded per §6.1. Resolution due before P2.

### OQ-P1-004: Binding manifest not yet signed
- **Id:** OQ-P1-004
- **Quote:** "0.5 binding_manifest.sha256 hashes of designated binding content; detached owner signature"
- **Impact:** The owner must create and sign the binding manifest. The agent proposes
  P1 catalogs; the owner approves and signs at the P1 Hard Stop. The manifest file
  does not exist yet and will be created by the owner after P1 review.
- **Status:** Recorded per §6.1 and §0.5.1 (manifest lifecycle).

### OQ-P1-005: Gitleaks not installed
- **Id:** OQ-P1-005
- **Quote:** "G1.5 Zero gitleaks findings; secrets baseline committed"
- **Impact:** gitleaks is not installed in the development environment. The secrets
  baseline (no committed credentials) is enforced by the .gitignore and manual review.
  gitleaks must be installed before owner-run verify_phase.sh.
- **Status:** Recorded; gitleaks installation is an infrastructure step.
