# P12 Hard-Stop Report — Core Determinism and Safety Hardening

## 1. PHASE

P12 — Core Determinism and Safety Hardening

**P12-code tag hash (full):** `ec68db5b77449b43be716f7a7ea97411b94f3087`
**P12-code tag hash (short):** `ec68db5`

## 2. DONE

### Deliverables with file paths

1. **Raw JSON ingestion at API edge (G12.1)**
   - `src/aminopstwin/gateway/raw_json.py` — `parse_raw_json()` with `object_pairs_hook=detect_duplicates`, `parse_float=reject_float`, `parse_constant=reject_constant`. Rejects duplicate keys (GW-INJ-003), floats (GW-INJ-004), NaN (GW-INJ-005), Infinity (GW-INJ-006), -Infinity (GW-INJ-007), malformed JSON (GW-INJ-008).
   - `tests/gateway/test_raw_json.py` — 29 tests (8 valid inputs, 6 float rejection, 2 NaN/Infinity, 4 duplicate key, 6 malformed, 2 determinism, 1 isolation).

2. **Two IdFactory implementations (G12.2)**
   - `src/aminopstwin/contracts/idfactory.py` — `DeterministicIdFactory` (HMAC-SHA256(seed, domain||counter) → UUID v4 layout), `EntropyIdFactory` (secrets.token_bytes), `step_id(workflow_id, step_no, attempt)`, `IdRegistry` with crash-recovery replay.
   - `tests/contracts/test_idfactory.py` — 24 tests (9 DeterministicIdFactory, 3 EntropyIdFactory, 5 step_id, 7 IdRegistry crash-recovery).

3. **TOCTOU for policy_epoch (G12.3)**
   - `src/aminopstwin/contracts/toctou.py` — `PolicyStateStore` with thread-safe atomic commit, `toctou_commit()` with retry/deny semantics, zero stale-epoch commits under concurrent advance.
   - `tests/contracts/test_toctou.py` — 13 tests (4 PolicyStateStore, 7 TOCTOU commit, 2 concurrency).

4. **StateFacts for Gateway (G12.4)**
   - `src/aminopstwin/contracts/state_facts.py` — Immutable `StateFacts` dataclass (idempotency_seen, budget_remaining, budget_limit, tenant_id, policy_epoch, policy_hash), `state_facts_hash()`.
   - `src/aminopstwin/contracts/decision.py` — Extended `DecisionRecord` with `state_facts_hash: str | None = None` (backward-compatible).
   - `src/aminopstwin/gateway/gateway.py` — `PolicyGateway.evaluate()` accepts `state_facts: StateFacts | None` and propagates hash into every DecisionRecord.
   - `tests/contracts/test_state_facts.py` — 11 tests (4 StateFacts, 2 DecisionRecord, 5 Gateway integration).

5. **Integer simulation time + named PRNG streams (G12.5)**
   - `src/aminopstwin/twin/integer_clock.py` — `MilliMinuteClock` (integer milliminutes, no floats), `NamedPrngStream` (H(seed, entity_name) keyed, integer Poisson via fixed-point Taylor series), `PrngRegistry` with entity isolation.
   - `tests/twin/test_integer_clock.py` — 23 tests (8 MilliMinuteClock, 10 NamedPrngStream, 5 PrngRegistry).

6. **Cross-platform state hash oracle (G12.5, Idea S4)**
   - `tests/twin/test_cross_platform_oracle.py` — 8 tests: deterministic simulation workload, platform detection, reproducibility, integer-only state, PRNG isolation, canonical serialization, waiver documentation.
   - `.github/workflows/ci.yml` — Test job now uses x86_64 + ARM64 matrix (ubuntu-latest, macos-14) with explicit cross-platform oracle step.

7. **Infrastructure**
   - `docs/gates.yaml` — G12.1–G12.5 added.
   - `scripts/check_commits.py` — G12.* added to GATE_IDS and PHASE_GATES["P12"].

### Commit count with capability/gate IDs

7 commits, all matching §21.3 regex:
- `9524d79` P12: implement raw JSON edge parser with exact rejection codes (G12.1)
- `4218ea1` P12: add DeterministicIdFactory and crash-safe step_id registry (G12.2)
- `0f3f500` P12: close TOCTOU for policy_epoch with atomic commit guard (G12.3)
- `5a45058` P12: add StateFacts snapshot and hash to DecisionRecord via Gateway (G12.4)
- `77a8f59` P12: add integer milliminute clock and named PRNG streams (G12.5)
- `78bb554` P12: add cross-platform state hash oracle test (G12.5, §119)
- `ec68db5` P12: add G12 gates, P12 phase gates, and CI cross-platform matrix (G12.1, G12.2, G12.3, G12.4, G12.5, INFRA)

## 3. NOT DONE

- **Cross-platform identity on x86_64**: only ARM64 (Apple Silicon) is available locally. CI runs on both x86_64 (ubuntu-latest) and ARM64 (macos-14) to verify cross-platform identity. Waiver documented in `tests/twin/test_cross_platform_oracle.py::test_waiver_documented_for_single_platform`.
- **Real ClinicalTrials.gov/AACT data ingestion**: not part of P12 (that is P13). P12 builds the determinism and safety infrastructure only.

## 4. DEVIATIONS

None. All deliverables implemented exactly as specified in `directive.txt` lines 92–134.

## 5. FAILED

No failing tests or gates.

## 6. MEASURED VALUES

| Gate | Description | Measured Value | Threshold | Pass? |
|------|-------------|----------------|-----------|-------|
| G12.1 | Raw JSON rejects duplicate keys and floats with exact codes | 29 passed | 1 (pass) | ✅ |
| G12.2 | Crash-recovery test produces no duplicate/orphan IDs | 24 passed | 1 (pass) | ✅ |
| G12.3 | TOCTOU test: 0 commits with stale epoch | 13 passed, 0 stale commits | 0 stale | ✅ |
| G12.4 | StateFacts hash present in every DecisionRecord | 11 passed | 1 (pass) | ✅ |
| G12.5 | Cross-platform state hash identical (or explicit waiver) | 31 passed | 1 (pass) | ✅ |
| — | Full regression (P1–P11 + P12) | 2465 passed, 0 failed | 0 failures | ✅ |
| — | mypy --strict (10 packages) | 0 errors | 0 | ✅ |
| — | ruff check (src/ + tests/) | All checks passed | 0 | ✅ |
| — | import-linter (Gateway purity) | 1 kept, 0 broken | 0 broken | ✅ |
| — | check_commits.py P12 | C2/C3/C4/C7 PASS | all pass | ✅ |

## 7. OPEN QUESTIONS

No open questions for P12. `docs/open_questions.md` has no P12-specific entries.

## 8. README STATUS

README.md already contains the Stage 2 active note (line 70–73):
> ### Stage 2 (P11–P14) Active
> Stage 2 is active with phases P11 through P14. P1–P10 are complete and closed.

P12 does not require a README update per the directive (only P11 and P14 do). STATUS remains CANDIDATE.

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction.
