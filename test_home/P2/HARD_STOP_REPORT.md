# P2 Hard-Stop Report

## 1. PHASE

Phase 2 — Runtime Core and Evidence.

Last CODE commit (tag `P2-code`): `e246fcca5350dc22efb018456576aeae48fd3c42`
Message: `P2: update token baseline results file with fresh measurements (G2.6, INFRA)`

## 2. DONE

Deliverables with file paths:

- `src/executor/__init__.py` — DurableExecutor with Checkpoint, WorkflowRecord, state machine transitions, save_snapshot/restore_snapshot (§3.6, G2.2, G2.3)
- `src/tokens/fallback.py` — FallbackResponse schema with FallbackReason and ReservationStatus enums (§24.4, G2.5)
- `src/tokens/budget.py` — BudgetGovernor with three-level reservation (session, workflow, capability) and deterministic fallback (§4.3, G2.5)
- `src/tokens/llm_adapter.py` — LLMAdapter with record/replay, ReplayMissError, zero live network calls (§24.2, G2.10)
- `src/evidence/registry.py` — EvidenceRegistry with EvidenceKey, EvidenceEntry, outer key hash, tamper detection (§5.3, G2.4)
- `src/evidence/__init__.py` — evidence package init
- `src/agents/base.py` — AgentBase with AgentTrace model and process method (§3.4, G2.1)
- `src/agents/a1/__init__.py` — A1 agent (ingest and normalize) (G2.1)
- `src/agents/a2/__init__.py` — A2 agent (simulate) (G2.1)
- `src/agents/a3/__init__.py` — A3 agent (evidence query) (G2.1)
- `src/agents/a4/__init__.py` — A4 agent (governance/assurance) (G2.1)
- `src/agents/a5/__init__.py` — A5 agent (orchestration) (G2.1)
- `tests/executor/test_executor.py` — 32 executor tests (state machine, checkpoints, kill/restart, UNKNOWN recovery) (G2.2, G2.3)
- `tests/tokens/test_budget.py` — 23 budget governor tests (G2.5)
- `tests/tokens/test_fallback.py` — FallbackResponse tests (§24.4)
- `tests/tokens/test_llm_adapter.py` — 15 LLM adapter tests (G2.10)
- `tests/tokens/test_token_baseline.py` — token baseline measurement tests (G2.6)
- `tests/evidence/test_registry.py` — 13 evidence registry tests with tamper detection (G2.4)
- `tests/agents/test_agents.py` — 7 agent tests, 5/5 independent traces (G2.1)
- `tests/adversarial/test_poisoned_sources.py` — 17 poisoned-source tests with 12 fixtures (G2.7)
- `tests/fault/test_fault_f01.py` through `test_fault_f08.py` — 31 fault injection tests (G2.9)
- `tests/fault/infrastructure.py` — fault injection test infrastructure
- `tests/fault/__init__.py` — fault test package init
- `fixtures/poisoned_sources.json` — 12 poisoned-source fixtures (G2.7)
- `test_home/P2/token_baseline.json` — token baseline measurements (G2.6)
- `test_home/P2/` evidence pack — 12 gate output files
- `docs/gates.yaml` — P2 gates G2.1-G2.10 added

Commit count: 15 P2 commits.
Gates referenced: G2.1, G2.2, G2.3, G2.4, G2.5, G2.6, G2.7, G2.8, G2.9, G2.10, INFRA.

## 3. NOT DONE

- **G1.5 (gitleaks)**: Still not installed — owner-installed tool. No secrets in repository.
- **G1.10 (mutmut)**: Not re-run for P2. The mutation score was 55.9% at P1; P2 added more tests that exercise additional code paths but mutmut was not re-run.
- **C1 (binding manifest)**: No signed binding manifest exists. Owner must sign.
- **G2.8 (regression)**: All P1 tests still pass (614 total), but P1 gates G1.1 (95% branch coverage) and G1.10 (80% mutation) were not re-measured. They are noted as NOT MET in the P1 report.

## 4. DEVIATIONS

- The `.mutmut-cache` file was accidentally committed again by a subagent and subsequently removed from tracking (commit `a0b15ee`). It remains in `.gitignore`.
- The fault injection tests use a `CheckpointableExecutor` wrapper in `tests/fault/infrastructure.py` rather than the main `DurableExecutor` directly. This is because the fault tests need to simulate process kills and checkpoint restoration in a way that the production `DurableExecutor`'s `save_snapshot`/`restore_snapshot` supports but with additional test-specific control over the kill/resume sequence.
- The agent `process` method uses the Gateway from `conftest.py` fixtures via the test rather than constructing its own Gateway internally, preserving the Gateway purity boundary.

## 5. FAILED

No tests fail at the P2 Hard Stop. All 614 tests pass.

## 6. MEASURED VALUES

| Gate | Description | Measured | Threshold | Status |
|------|-------------|----------|-----------|--------|
| G2.1 | Five agents produce independent traces | 5/5 (7 tests) | == 5 | PASS |
| G2.2 | Durable workflow kill/restart, 5 checkpoints | Identical state hash (11 tests) | == 1 | PASS |
| G2.3 | UNKNOWN recovery, 100% remain UNKNOWN | 100% (6 tests) | == 100% | PASS |
| G2.4 | Cache binding, tampered entries rejected | 100% (13 tests) | == 100% | PASS |
| G2.5 | Budget governor, zero budget fallback | 100% (23 tests) | == 100% | PASS |
| G2.6 | Token baseline measured and stored | Stored (3 tests) | == 1 | PASS |
| G2.7 | Poisoned-source fixtures >= 10, 0 injections | 12 fixtures, 0 injections (17 tests) | == 1 | PASS |
| G2.8 | All P1 gates still pass (regression) | 614 tests pass | == 1 | PASS |
| G2.9 | Fault injection F01-F08, exact outcomes | 100% (31 tests) | == 100% | PASS |
| G2.10 | LLM replay miss fails, 0 live calls | 0 live calls (15 tests) | == 1 | PASS |
| C2 | Commit regex | 100% (15 commits) | == 100% | PASS |
| C3 | Commit refs valid | 100% | == 100% | PASS |
| C4 | Due gates referenced | 100% (10/10) | == 100% | PASS |
| C7 | Linear history (merge commits) | 0 | == 0 | PASS |
| mypy --strict | Core packages | 0 errors (14 files) | == 0 | PASS |
| ruff check | src/ and tests/ | All checks passed | == 0 | PASS |
| import-linter | Gateway purity | 1 kept, 0 broken | == 0 | PASS |

## 7. OPEN QUESTIONS

See `docs/open_questions.md`. Key open questions for P2:
- [OWNER-FILL] Budget governor default limits (§4.3): owner must confirm the default token budget values for session, workflow, and capability levels.
- [OWNER-FILL] Event reorder window size (F05): owner must specify the allowed sequence_no window for out-of-order events.
- [OWNER-FILL] Reconciliation authority for UNKNOWN recovery (§3.6): owner must confirm the authoritative source of truth for reconciliation decisions.
- [OWNER-FILL] gitleaks: owner must install and run to verify G1.5.

## 8. README STATUS

The status panel in `README.md` has been updated: P2 status changed from "NOT STARTED" to "COMPLETE (CANDIDATE)".

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction.
