<div align="center">

# AminOpsTwin

**Operational Cognitive Digital Twin for Clinical Research Operations**

Capacity planning · Queues · Scheduling · Bottleneck analysis · Operational what-if

**STATUS: CANDIDATE** — P1–P24 governance and in-memory implementation complete; all 60 capabilities SPECIFIED, none yet IMPLEMENTED or VERIFIED

</div>

---

## Mission

AminOpsTwin is a non-medical **operational** cognitive digital twin for clinical
**research operations** — it models capacity, flow, and contention so teams can
reason about what-if scenarios without touching production. [CLAIM-001] It uses
synthetic operational data and licensed public research material only. [CLAIM-003]
It is not a medical device, does not perform diagnosis, prognosis, treatment, or
dose recommendation, and never models individual patient state. [CLAIM-006]

## What It Is Not

- Not a medical decision system [CLAIM-006]
- Not clinically validated [CLAIM-009]
- Not production-ready [CLAIM-009]
- Not synchronized with a real organization [CLAIM-010]
- Does not use real patient or participant data [CLAIM-008]
- No persistence until P27 (in-memory state machine)
- No real RLS until P27 (in-memory simulation)
- No authentication or authorization until P33
- No asymmetric signatures until P32 (HMAC integrity tags only)

## Status Model

Three levels govern every phase and capability (see [docs/status_model.md](docs/status_model.md)):

| Level | Meaning | Who sets it |
|-------|---------|-------------|
| **GOVERNANCE** | Process artefacts exist (directive, gates, ADRs, capability catalog) | Agent |
| **IMPLEMENTED** | Code and tests exist and pass | Agent |
| **VERIFIED** | Independent review and green CI confirm the implementation | Owner only |

All 60 capabilities in [docs/capability_catalog.yaml](docs/capability_catalog.yaml) are
**SPECIFIED** — governance artefacts exist. None is yet **IMPLEMENTED** or
**VERIFIED**. That statement stays until real phases change it.

## Phase Status

| Phase | Level | Evidence |
|-------|-------|---------|
| P1 | GOVERNANCE | [test_home/P1/](test_home/P1/) |
| P2 | GOVERNANCE | [test_home/P2/](test_home/P2/) |
| P3 | GOVERNANCE | [test_home/P3/](test_home/P3/) |
| P4 | GOVERNANCE | [test_home/P4/](test_home/P4/) |
| P5 | GOVERNANCE | [test_home/P5/](test_home/P5/) |
| P6 | GOVERNANCE | [test_home/P6/](test_home/P6/) |
| P7 | GOVERNANCE | [test_home/P7/](test_home/P7/) |
| P8 | GOVERNANCE | [test_home/P8/](test_home/P8/) |
| P9 | GOVERNANCE | [test_home/P9/](test_home/P9/) |
| P10 | GOVERNANCE | [test_home/P10/](test_home/P10/) |
| P11 | GOVERNANCE | [test_home/P11/](test_home/P11/) |
| P12 | GOVERNANCE | [test_home/P12/](test_home/P12/) |
| P13 | GOVERNANCE | [test_home/P13/](test_home/P13/) |
| P14 | GOVERNANCE | [test_home/P14/](test_home/P14/) |
| P15 | GOVERNANCE | [test_home/P15/](test_home/P15/) |
| P16 | GOVERNANCE | [test_home/P16/](test_home/P16/) |
| P17 | GOVERNANCE | [test_home/P17/](test_home/P17/) |
| P18 | GOVERNANCE | [test_home/P18/](test_home/P18/) |
| P19 | GOVERNANCE | [test_home/P19/](test_home/P19/) |
| P20 | GOVERNANCE | [test_home/P20/](test_home/P20/) |
| P21 | GOVERNANCE | [test_home/P21/](test_home/P21/) |
| P22 | GOVERNANCE | [test_home/P22/](test_home/P22/) |
| P23 | GOVERNANCE | [test_home/P23/](test_home/P23/) |
| P24 | GOVERNANCE | [test_home/P24/](test_home/P24/) |
| P25 | IN PROGRESS | [reports/P25/](reports/P25/) |

## Non-Negotiable Invariants

| Principle | Enforcement | Verification |
|-----------|-------------|--------------|
| Deny-by-default | Gateway returns DENY for any unrecognised input | G1.4 |
| Gateway purity | Same inputs produce identical outputs; no network or LLM imports | G1.2, G1.7 |
| Deterministic replay | Identical seeds produce identical state hashes across replays | G3.1, G16.1 |
| Cross-platform determinism | State hashes match on x86_64 and ARM64 | G12.5, G16.2 |
| No floating-point in hashed state | Fixed-point integers only on the hashed state path | N-15, G16.4 |
| Canonical serialization | `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)` | G1.11 |
| No real patient data | Synthetic data and public aggregates only | CLAIM-008, G4.3 |
| Non-medical boundary | No diagnosis, prognosis, treatment, or dose recommendation | CLAIM-006 |
| Quota enforcement | Over-budget requests denied with GW-BUDGET-001 | G18.2 |
| Tenant isolation | Zero cross-tenant leakage; RLS simulated until P27 | G5.2, G18.3 |

## System Flow

```
         ┌──────────────────────────────────────────────────────────────┐
         │                      Envelope (§3.5)                          │
         │  schema_id · envelope_type · tenant_id · policy_epoch ·        │
         │  correlation_id · idempotency_key · payload · payload_hash     │
         └──────────────────────┬───────────────────────────────────────┘
                                │
         ┌──────────────────────▼───────────────────────────────────────┐
         │                    Agents (A1–A5)                            │
         │  Each agent issues typed envelopes with correlation_id         │
         └──────────────────────┬───────────────────────────────────────┘
                                │
         ┌──────────────────────▼───────────────────────────────────────┐
         │               Policy Gateway (S1) — deny-by-default            │
         │  schema → epoch → authorization → invariant → budget → ALLOW │
         │                          or DENY + reason_code                  │
         └──────────┬───────────────────────────────────┬───────────────┘
                    │ ALLOW                             │ DENY
         ┌──────────▼──────────────┐    ┌──────────────▼──────────────┐
         │  Durable Executor (S2)  │    │   Reason Code + Audit Log    │
         │  PENDING → RUNNING →    │    │   GW-<DOMAIN>-<NNN>           │
         │  CHECKPOINTED →         │    └──────────────────────────────┘
         │  COMMIT_INTENT →        │
         │  COMMITTED → COMPLETED  │
         └──────────┬─────────────┘
                    │ committed effect
         ┌──────────▼──────────────┐
         │  Evidence Registry      │
         │  claim graph · Merkle   │
         │  pack · audit chain     │
         └─────────────────────────┘
```

Five agents (A1–A5) issue typed envelopes that pass through the deny-by-default
Policy Gateway (S1), then the Durable Executor (S2). [CLAIM-004] No agent holds a
direct handle to the database or the Executor store. [CLAIM-005]

## Contaminated Context Control

```
  Input payload
       │
       ▼
  ┌─────────────┐     patient-level field?       ┌─────────┐
  │  Pre-filter  │──────────────────────────────►│  DENY    │
  │  (tokens)   │     non-aggregate content?   │ GW-CLIN  │
  └──────┬──────┘     forbidden pattern?       └─────────┘
         │ pass
         ▼
  ┌─────────────┐     schema mismatch?           ┌─────────┐
  │  Schema     │──────────────────────────────►│  DENY    │
  │  validator  │     non-NFC string?          │ GW-SCHEMA│
  └──────┬──────┘     lone surrogate?          └─────────┘
         │ pass
         ▼
  ┌─────────────┐     epoch stale?             ┌─────────┐
  │  Gateway    │     principal unknown?       │  DENY    │
  │  (S1)       │     quota exceeded?          │  +reason │
  └──────┬──────┘     invariant violated?      └─────────┘
         │ ALLOW
         ▼
    Executor (S2)
```

Every envelope traverses pre-filter, schema validation, and the deny-by-default
Gateway before reaching the Executor. The Gateway never queries time, network, or
mutable storage internally — it is a pure function. Contaminated or non-conforming
input is denied at the earliest stage with a precise reason code. No patient-level
data, non-aggregate content, or forbidden pattern reaches the deterministic core.
[CLAIM-004]

## Maturity Ladder

| Stage | Description | Status |
|-------|-------------|--------|
| **Model** | Synthetic data, deterministic simulation, operational what-if | **Current** |
| Shadow | Side-by-side with live aggregate data, no committed effects | Future (P34) |
| Twin | Real-time mirror with live operational state | Future |

AminOpsTwin is currently at the **Model** stage. All data is synthetic or derived
from licensed public research aggregates. No live operational data is ingested.
The Shadow and Twin stages are future work requiring approved data sources and
additional governance.

## Measured Summary

Latest full regression: **3088 tests passed, 7 skipped, 9 failed** (P25 baseline,
October 2026). The 9 failures are known baseline exceptions from the retired
Stage 4 directive tests, listed in [reports/P25/PROGRESS.md](reports/P25/PROGRESS.md).
Every claim-id in this README resolves via the standalone verify CLI
without running the full system. [CLAIM-016]

## Safety Boundaries

AminOpsTwin operates within strict non-medical safety boundaries. It performs no
diagnosis, prognosis, treatment, or dose recommendation. It never models
individual patient state. It uses no real patient or participant data. It is not
synchronized with a real organization. It is not clinically validated and not
production-ready. All outputs are operational planning aids derived from synthetic
data and public research aggregates. The deny-by-default Gateway enforces these
boundaries at the protocol level — no input bypasses the Gateway to reach the
Executor. [CLAIM-006] [CLAIM-008] [CLAIM-009] [CLAIM-010]

See [docs/regulatory/intended_purpose.md](docs/regulatory/intended_purpose.md)
for the operational intended purpose record and explicit exclusions.

## Hard-Stop Reports

Every phase concludes with a Hard-Stop Report stored under `test_home/P<n>/`
(P1–P24) or `reports/P<n>/` (P25+):

| Phase | Report |
|-------|--------|
| P1–P24 | `test_home/P<n>/HARD_STOP_REPORT.md` |
| P25 | [reports/P25/](reports/P25/) |

## Technology

- Python 3.12+, FastAPI, Pydantic v2, PyYAML
- Hypothesis (property-based testing), schemathesis (API fuzzing)
- ruff (with DTZ + TID251 banned-api) + mypy --strict, import-linter
- deptry (dependency truth), gitleaks, pip-audit, CycloneDX (SBOM)
- uv for venv and dependency management

PostgreSQL, SQLAlchemy, Alembic, SimPy, and NetworkX are not yet used.
They return in the phases that actually need them (P27, P29).

## Architecture

Package layout (all modules under `src/aminopstwin/`):

- `contracts/` — envelopes, schemas, reasons, Clock, IdFactory
- `gateway/` — Policy Gateway (no LLM or network imports), quota enforcement
- `executor/` — in-memory state machine with checkpointing (no durability until P27)
- `agents/` — five agents (A1–A5)
- `twin/` — entities, temporal state, simulation, delta compression
- `evidence/` — registry, cache binding, impact tracking, Merkle pack, audit chain, claim graph
- `tokens/` — pre-filter, templates, budget governor, LLM adapter
- `assurance/` — weekly scheduler, zero-model assurance, integrity-tagged pack, telemetry, drift detection
- `dashboard/` — views, app, wallboard, accessibility (no auth until P33)
- `enterprise/` — tenant isolation, evaluation, manifest, transparency, RLS (simulated until P27)
- `integration/` — backup, deployment, exports (integrity tag, not asymmetric signature)
- `priors/` — deterministic prior pack from public aggregates
- `ingestion/` — shadow-mode ingestion gateway (Data Contract v1)
- `shadow_pilot.py` — sample Shadow Pilot report (module, not a package)
- `fixtures_gen/` — synthetic data generator
- `policy_simulation.py` — policy simulation mode
- `retention.py` — retention configuration
- `scheduling.py` — scheduling configuration
- `stage_seal.py` — Stage 3 seal (integrity tag)
- `stage4_seal.py` — Stage 4 seal (integrity tag)
- `api/` — read-only aggregate API (no auth until P33)

Five agents (A1–A5), two deterministic shared services (S1 Policy Gateway, S2
Durable Executor). Every action passes through S1, then S2. [CLAIM-004] No agent
holds a direct handle to the database or the Executor store. [CLAIM-005]

## Honesty

> Honesty is a person's greatest asset, regardless of their position or work.

All claims remain Candidate until independently verified by approved evidence.
No status in this README exceeds what the evidence supports.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Author

Amin Azimi | End-to-End System AI Architect | End-to-End System Development
Azimi Innovation Lab | azimilab2025@gmail.com

Project start: October 2026.

## License

Copyright 2026 Amin Azimi / Azimi Innovation Lab. All rights reserved.
Publication of this work grants no license of any kind. See [LICENSE](LICENSE).
