# P17 Hard-Stop Report — Provable Evidence Graph and Auditability

## 1. PHASE

P17 — Provable Evidence Graph and Auditability

Last CODE commit: 31fd44b (P17: add G17 gate IDs, phase gates, and gates.yaml
entries for evidence graph)

## 2. DONE

### Deliverables

- **Claim graph** with `depends_on` in `claims.yaml` and stale claim detection
  — `src/aminopstwin/evidence/claim_graph.py`
  — Gate G17.1
  — Test: `tests/p17/test_claim_graph.py`

- **Merkle evidence pack** with partial proof generation and verification
  — `src/aminopstwin/evidence/merkle_pack.py`
  — Gate G17.2
  — Test: `tests/p17/test_merkle_pack.py`

- **Temporal versioning** with append-only claim history
  — `src/aminopstwin/evidence/temporal_versioning.py`
  — Gate G17.3
  — Test: `tests/p17/test_audit_chain.py`

- **Audit hash-chain** with `prev_hash + record_hash`, offline CLI
  — `src/aminopstwin/evidence/audit_chain.py`
  — Gate G17.3
  — Test: `tests/p17/test_audit_chain.py`

- **Offline verification kit** (`scripts/verify_pack.py`)
  — Gate G17.4
  — Test: `tests/p17/test_offline_kit.py`

- **Full regression** (G17.5)
  — Test: `tests/p17/test_regression.py`

### Commits

1. 31fd44b — P17: add G17 gate IDs, phase gates, and gates.yaml entries for
   evidence graph (G17.1, G17.2, G17.3, G17.4, G17.5, INFRA)

Note: P17 source modules were added in commits between the P16 and P18
phases. The P17-prefixed commit (31fd44b) added the gate infrastructure.
The source and test files were tracked in git as part of the working tree
during the P17 development cycle.

## 3. NOT DONE

None — all P17 deliverables are complete.

## 4. DEVIATIONS

- P17 source and test files were committed without P17-prefixed commit
  messages during the original development cycle. The gate infrastructure
  commit (31fd44b) is the only P17-prefixed commit. This is a commit
  discipline deviation from §21.

## 5. FAILED

None — all P17 gates pass.

## 6. MEASURED VALUES

- G17.1 (stale claim detection): PASS
- G17.2 (Merkle partial proof): PASS
- G17.3 (audit hash-chain + temporal versioning): PASS
- G17.4 (offline verification kit): PASS
- G17.5 (full regression): PASS — 0 failures

## 7. OPEN QUESTIONS

None.

## 8. README STATUS

README updated — P17 is marked COMPLETE (CANDIDATE) in the phase status
table with evidence link to test_home/P17/.

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction.
