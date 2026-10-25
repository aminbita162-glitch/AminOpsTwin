# P18 — Hard-Stop Report

## 1. Phase + hash of last CODE commit

**Phase:** P18 — Enforceable Controls and Observability

**P18-code tag hash:**
- Full: `7e2186643...` (run `git rev-parse P18-code` for exact value)
- Short: `7e21866`

## 2. DONE

### Deliverables

1. **Isolation suite** (G18.1)
   - `src/aminopstwin/enterprise/isolation.py` — `TenantIsolationSuite`, `IsolationResult` (frozen dataclass), `run_isolation_suite()`. Runs N concurrent tenant operations via threads; each tenant gets its own `MemoryStore`/`DurableExecutor`/`TenantGuard`/`IdFactory`. Checks: shared-state independence, cross-log leakage (zero), timing side-channel (zero).
   - `tests/p18/test_isolation.py` — 16 tests
   - Commit: `P18: add isolation suite for concurrent tenant isolation and side-channel checks (G18.1)`

2. **Quota engine** (G18.2)
   - `src/aminopstwin/gateway/quota.py` — `TenantQuotaEngine` (thread-safe per-tenant quota tracker) and `QuotaAwareGateway` (wraps `PolicyGateway`, checks quota before delegating; over-budget returns DENY `DecisionRecord` with `reason_code='GW-BUDGET-001'`, `stage=Stage.BUDGET`).
   - `src/aminopstwin/gateway/__init__.py` — updated with quota exports
   - `tests/p18/test_quota.py` — 17 tests
   - Commit: `P18: add tenant quota engine and quota-aware Gateway for budget enforcement (G18.2)`

3. **PostgreSQL RLS** (G18.3)
   - `src/aminopstwin/enterprise/rls.py` — `RLSPolicy`, `RLSEngine` (in-memory RLS simulation keyed on `tenant_id`), `generate_executor_rls_policies()` for executor tables (`workflow_records`, `checkpoints`). `select()` returns only the requesting tenant's records; zero leakage.
   - `src/aminopstwin/enterprise/__init__.py` — updated with RLS + isolation exports
   - `tests/p18/test_rls.py` — 16 tests
   - Commit: `P18: add PostgreSQL RLS simulation with executor table policies and zero-leakage tests (G18.3)`

4. **Assurance report** (G18.4)
   - `src/aminopstwin/assurance/signed_pack.py` — `SignedAssurancePack`, `PackManifest`, `GateStatus`, `DriftMetrics`, `generate_signed_pack()`, `verify_signed_pack()`. Pack contains gate status, claim summary, drift metrics (integer-scaled), assurance report, Merkle root, HMAC-SHA256 signature. Validates with offline kit.
   - `src/aminopstwin/assurance/__init__.py` — updated with signed pack, telemetry, drift exports
   - `tests/p18/test_assurance_pack.py` — 12 tests
   - Commit: `P18: add signed assurance Evidence Pack with Merkle root and HMAC signature verification (G18.4)`

5. **Secure telemetry** (G18.5)
   - `src/aminopstwin/assurance/telemetry.py` — `TelemetryField`, `TelemetryAllowList`, `TelemetryExporter`, `TelemetryCanary`. Allow-list (trace_id, span_id, operation, tenant_id, duration_ms, outcome, timestamp); sensitive fields (secret, password, token, api_key, payload) excluded. Canary secret detection via recursive scan.
   - `tests/p18/test_telemetry.py` — 35 tests
   - Commit: `P18: add secure telemetry allow-list and canary secret detection for exported spans (G18.5)`

6. **Drift detection** (G18.5)
   - `src/aminopstwin/assurance/drift.py` — `DriftMetric`, `DriftAlert`, `DriftDetector`. Tracks state hash changes and denial rates against thresholds; emits structured `DriftAlert` records with severity (WARNING/CRITICAL).
   - `tests/p18/test_drift.py` — 33 tests
   - Commit: `P18: add drift detection for state hash changes and denial rate thresholds (G18.5)`

### Infrastructure

- `scripts/check_commits.py` — G18.1–G18.5 gate IDs + P18 phase gates
- `docs/gates.yaml` — P18 gate entries (G18.1–G18.5)
- `tests/p18/test_regression.py` — full regression test with nested guard propagation
- `test_home/P18/full_regression.txt` — full regression output

### Commit count

10 commits (1 INFRA + 6 deliverables + 1 regression test + 1 README + 1 pre-existing fix).

### Gates referenced

G18.1, G18.2, G18.3, G18.4, G18.5 — all referenced in commits.

## 3. NOT DONE

None. All 6 deliverables are complete with implementation, tests, gate entries, and evidence.

## 4. DEVIATIONS

- The `DriftMetrics` dataclass in `signed_pack.py` uses integer-scaled values (`state_hash_stability_scaled`, `denial_rate_scaled` — ×10 000) instead of floats to comply with N-15 (no float in canonical payloads). This is a design constraint, not a deviation.
- Pre-existing ruff E741 (`l` variable in `merkle_pack.py:tree_to_dict`) and mypy `type: ignore` issue in `claim_graph.py` were fixed as INFRA commits since they blocked P18 quality gates.
- The RLS deliverable uses an in-memory simulation of PostgreSQL RLS because PostgreSQL is not available in the test environment (the project uses SQLite for offline demo). The `RLSEngine` simulates RLS policies keyed on `tenant_id` with the same semantics.

## 5. FAILED

None. All tests pass.

## 6. MEASURED VALUES

| Gate | Metric | Measured | Threshold | Pass |
|------|--------|----------|-----------|------|
| G18.1 | isolation_suite_pass | 16 passed | 1 | PASS |
| G18.2 | quota_enforced_pass | 17 passed | 1 | PASS |
| G18.3 | rls_zero_leakage_pass | 16 passed | 1 | PASS |
| G18.4 | assurance_pack_valid_pass | 12 passed | 1 | PASS |
| G18.5 | full_regression_pass | 2845 passed, 4 skipped, 0 failed | 1 | PASS |

### Quality gates

| Check | Result |
|-------|--------|
| `ruff check src/aminopstwin/ tests/` | All checks passed! |
| `mypy --strict` (85 source files) | Success: no issues found in 85 source files |
| `lint-imports` | 2 kept, 0 broken (Gateway purity + Layer independence) |
| `check_commits.py P18` | ALL COMMIT CHECKS PASS (10 commits) |

### Per-gate test counts

| Gate | Test file | Tests passed |
|------|-----------|-------------|
| G18.1 | tests/p18/test_isolation.py | 16 |
| G18.2 | tests/p18/test_quota.py | 17 |
| G18.3 | tests/p18/test_rls.py | 16 |
| G18.4 | tests/p18/test_assurance_pack.py | 12 |
| G18.5 | tests/p18/test_telemetry.py | 35 |
| G18.5 | tests/p18/test_drift.py | 33 |
| G18.5 | tests/p18/test_regression.py | 1 (full suite: 2845 passed, 4 skipped) |

## 7. OPEN QUESTIONS

No P18-specific open questions. (`grep -c 'OQ-P18' docs/open_questions.md` = 0)

## 8. README STATUS

README.md updated:
- Phase status table: P17 and P18 now show COMPLETE (CANDIDATE); P19–P20 show NOT STARTED.
- Hard-Stop Reports: P17 and P18 links added.
- Measured summary: "2845 tests passed, 4 skipped, 0 failures (P18 regression)."
- Architecture diagram: gateway, evidence, assurance, enterprise descriptions updated with P18 capabilities.

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction. Do not start P19.
