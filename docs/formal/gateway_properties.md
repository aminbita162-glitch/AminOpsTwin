# Gateway Properties — Formal Sketch (P20, G20.1)

This document outlines the formal properties of the Policy Gateway (S1)
and the surrounding deterministic core.  Each property is stated as an
argument or model snippet and references the **concrete code location**
that implements or enforces it.

## 1. Deny-by-default

**Property.** For every input that is not explicitly authorised by the
policy matrix, the Gateway returns a `DENY` decision with a non-empty
`reason_code`.  No input is implicitly admitted.

**Argument.** The `PolicyGateway.evaluate` method in
`src/aminopstwin/gateway/gateway.py` (line 149) checks, in order:

1. **Schema membership** — if `envelope.schema_id` is not in
   `self._schema_registry`, it returns `DENY` with `GW-DEFAULT-001`
   (line 173).
2. **Schema type match** — if the `envelope_type` does not match the
   registry's expected type, it returns `DENY` with `GW-DEFAULT-001`
   (line 191).
3. **Epoch check** — if `envelope.policy_epoch` is less than or
   greater than `self._current_epoch`, it returns `DENY` with
   `GW-EPOCH-001` or `GW-EPOCH-002` (lines 210, 225).
4. **Authorization matrix** — `PolicyMatrix.is_allowed` (line 109)
   iterates over the allow-list entries and returns `False` if no
   `(principal, envelope_type, capability)` triple matches.  The
   Gateway then returns `DENY` with `GW-AUTH-001` (line 240).

Only if every check passes does the method return `ALLOW` (line 259).
There is no code path that returns `ALLOW` without passing all four
checks — the default is `DENY`.

**Test evidence.** `tests/gateway/test_deny_default.py` (G1.4)
verifies that an unknown `schema_id` / `envelope_type` / action yields
`GW-DEFAULT-001`.  `tests/gateway/test_gateway_purity.py` (G1.2)
verifies that 1000 repeated calls on the same input produce the same
output.

## 2. No Gateway state leakage

**Property.** The Gateway is a pure function: it holds no mutable state
that depends on prior calls.  The same inputs always produce the same
`DecisionRecord`.  The Gateway never queries time, the network, or
mutable storage internally.

**Argument.**

- `PolicyGateway.__init__` (line 131) stores only the `PolicyMatrix`,
  `current_epoch`, `schema_registry`, and `envelope_type_registry` —
  all immutable after construction.
- `PolicyGateway.evaluate` (line 149) reads from `self._policy_matrix`,
  `self._current_epoch`, `self._schema_registry`, and
  `self._envelope_type_registry` — none of which are mutated during
  evaluation.  The `decided_at` parameter is injected by the caller;
  the Gateway does not call `datetime.now()` internally.
- The import-linter contract "Gateway purity: no LLM-library or network
  imports" in `pyproject.toml` (line 112) forbids `openai`,
  `anthropic`, `langchain`, `httpx`, `requests`, `aiohttp`, `urllib`,
  `socket`, etc. from `aminopstwin.gateway`.  This is enforced by
  `lint-imports` in CI.

**Test evidence.** `tests/gateway/test_gateway_purity.py` (G1.2)
verifies purity with 1000 repeated calls.
`tests/arch/` contains a canary test that intentionally violates the
import boundary and is expected to fail (G15.4).

## 3. Rejection of non-aggregate payloads

**Property.** The Data Contract and the read-only API reject any payload
that contains patient-level (individual) fields.  Only aggregate metrics
are admitted.

**Argument.**

- `PATIENT_LEVEL_FIELDS` in
  `src/aminopstwin/contracts/data_contract.py` (line 115) defines the
  forbidden field set: `patient_id`, `patient_name`, `diagnosis`,
  `prognosis`, `treatment`, `dose`, `individual_risk`,
  `health_status`.
- `_check_patient_fields` (line 184) raises `DataContractError` if any
  patient-level field is present in a record.
- `validate_record_v1` (line 194) and `validate_record_v2` (line 208)
  both call `_check_patient_fields` before Pydantic validation.
- `AggregateAPI.get_record` in
  `src/aminopstwin/api/__init__.py` (line 292) returns a 403 RFC 9457
  problem detail if the requested `field` is in
  `PATIENT_LEVEL_FIELDS` (line 315).
- `AggregateAPI.validate_all_records` (line 351) raises if any
  patient-level field is present in any backing record.

**Test evidence.** `tests/p19/test_data_contract.py` (G19.1) verifies
that patient-level fields are rejected.
`tests/p19/test_api.py` (G19.3) verifies that the API returns 403 for
non-aggregate retrieval attempts.

## 4. Deterministic replay identity

**Property.** Identical inputs to the deterministic core produce
identical state hashes across replays, processes, and architectures.

**Argument.**

- `canonical_bytes` in
  `src/aminopstwin/contracts/canonical.py` serialises payloads with
  `sort_keys=True, separators=(',', ':'), ensure_ascii=False,
  allow_nan=False` — a deterministic, architecture-independent
  byte encoding.
- `canonical_hash` computes SHA-256 over `canonical_bytes` — an
  integer-only hash that is identical on x86_64 and ARM64.
- The `SeededClock` and `DeterministicIdFactory` in
  `src/aminopstwin/contracts/clock.py` and
  `src/aminopstwin/contracts/idfactory.py` provide deterministic
  time and ID generation.
- The `MilliMinuteClock` and fixed-point numeric type in
  `src/aminopstwin/twin/integer_clock.py` and
  `src/aminopstwin/twin/fixed_point.py` ensure that no float enters
  any hashed state path.

**Test evidence.** `tests/twin/test_cross_platform_oracle.py`
(G12.5, G16.2) verifies identical hashes across platforms.
`tests/twin/test_simulation.py` (G3.1, G16.1) verifies replay identity.

## 5. Quota enforcement at the Gateway

**Property.** The Gateway checks tenant budget before allowing any
Executor submission.  Over-budget requests receive `GW-BUDGET-001`.

**Argument.**

- `QuotaAwareGateway.evaluate` in
  `src/aminopstwin/gateway/quota.py` (line 112) checks
  `self._quota.check_quota(envelope.tenant_id)` *before* delegating to
  the wrapped `PolicyGateway`.
- If the quota is exhausted, it returns `DENY` with
  `GW-BUDGET-001` and `Stage.BUDGET` (line 126) without invoking the
  underlying gateway.

**Test evidence.** `tests/p18/test_quota.py` (G18.2) verifies that
over-budget requests are denied at the Gateway.

## References

| Property | Code location | Test |
|----------|---------------|------|
| Deny-by-default | `src/aminopstwin/gateway/gateway.py:149` | G1.4 |
| No state leakage | `src/aminopstwin/gateway/gateway.py:131` | G1.2 |
| Non-aggregate rejection | `src/aminopstwin/contracts/data_contract.py:184` | G19.1, G19.3 |
| Replay identity | `src/aminopstwin/contracts/canonical.py` | G12.5, G16.1 |
| Quota enforcement | `src/aminopstwin/gateway/quota.py:112` | G18.2 |
