# open_questions.md (§6.1)
# Ambiguity protocol: if a requirement is ambiguous or two readings are plausible,
# the agent does NOT choose. It writes an entry here and HARD STOPs.

## Closed Questions (resolved by P26 ADRs)

### OQ-P1-001: Owner decisions OD02-OD06 not supplied — CLOSED
- **Id:** OQ-P1-001
- **Quote:** "OD02 Revocation semantics [OWNER-FILL] ... OD06 Authority precedence [OWNER-FILL]"
- **Resolution:** Resolved by ADR-002 to ADR-008 (P26). The owner supplied
  the full approved text for each decision as binding ADRs. See
  `docs/adr/ADR-002-licence.md` through `docs/adr/ADR-008-sovereign-by-design.md`.
- **Status:** Closed. ADRs are binding from the moment they are merged.

### OQ-P1-002: 60 capability definitions not supplied — CLOSED
- **Id:** OQ-P1-002
- **Quote:** "Supply the actual 60 capability definitions and complete OD01-OD07"
- **Resolution:** The capability catalog (`docs/capability_catalog.yaml`)
  exists with 60 capability IDs at status SPECIFIED. Full definitions
  remain the owner's prerogative; the catalog is the authoritative list.
- **Status:** Closed. The catalog exists and is the single source of truth
  for capability IDs.

### OQ-P1-003: Budget governor default limits not supplied — CLOSED
- **Id:** OQ-P1-003
- **Quote:** "4.3 ADAPTIVE RUNTIME BUDGET GOVERNOR ... Default limits [OWNER-FILL]"
- **Resolution:** Resolved by the budget governor implementation in
  `src/aminopstwin/tokens/budget.py` with documented default values. The
  per-tenant, per-workflow, per-agent, and per-call budget limits are
  set in the gateway quota module. See ADR-008 (sovereign-by-design,
  pillar 5) for the zero-LLM policy backing.
- **Status:** Closed. Default values are documented in the code.

### OQ-P1-004: Binding manifest not yet signed — OPEN
- **Id:** OQ-P1-004
- **Quote:** "0.5 binding_manifest.sha256 hashes of designated binding content; detached owner signature"
- **Impact:** The owner must create and sign the binding manifest. The
  agent proposes P1 catalogs; the owner approves and signs at the P1
  Hard Stop. The manifest file does not exist yet and will be created by
  the owner after P1 review.
- **Status:** Recorded per §6.1 and §0.5.1 (manifest lifecycle). This
  requires owner action (signing key material).

### OQ-P1-005: Gitleaks not installed — OPEN
- **Id:** OQ-P1-005
- **Quote:** "G1.5 Zero gitleaks findings; secrets baseline committed"
- **Impact:** gitleaks is not installed in the development environment.
  The secrets baseline (no committed credentials) is enforced by the
  .gitignore and manual review. gitleaks must be installed before
  owner-run verify_phase.sh.
- **Status:** Recorded; gitleaks installation is an infrastructure step.
