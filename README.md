<div align="center">

# AminOpsTwin

**Operational Cognitive Digital Twin for Clinical Research Operations**

Capacity planning · Queues · Scheduling · Bottleneck analysis · Operational what-if

**STATUS: CANDIDATE** — Stage 4 (P21–P24) active · Stage 3 (P15–P20) complete · P1–P20 COMPLETE (CANDIDATE)

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

## Phase Status

| Phase | Status | Evidence |
|-------|--------|----------|
| P1 | COMPLETE (CANDIDATE) | [test_home/P1/](test_home/P1/) |
| P2 | COMPLETE (CANDIDATE) | [test_home/P2/](test_home/P2/) |
| P3 | COMPLETE (CANDIDATE) | [test_home/P3/](test_home/P3/) |
| P4 | COMPLETE (CANDIDATE) | [test_home/P4/](test_home/P4/) |
| P5 | COMPLETE (CANDIDATE) | [test_home/P5/](test_home/P5/) |
| P6 | COMPLETE (CANDIDATE) | [test_home/P6/](test_home/P6/) |
| P7 | COMPLETE (CANDIDATE) | [test_home/P7/](test_home/P7/) |
| P8 | COMPLETE (CANDIDATE) | [test_home/P8/](test_home/P8/) |
| P9 | COMPLETE (CANDIDATE) | [test_home/P9/](test_home/P9/) |
| P10 | COMPLETE (CANDIDATE) | [test_home/P10/](test_home/P10/) |
| P11 | COMPLETE (CANDIDATE) | [test_home/P11/](test_home/P11/) |
| P12 | COMPLETE (CANDIDATE) | [test_home/P12/](test_home/P12/) |
| P13 | COMPLETE (CANDIDATE) | [test_home/P13/](test_home/P13/) |
| P14 | COMPLETE (CANDIDATE) | [test_home/P14/](test_home/P14/) |
| P15 | COMPLETE (CANDIDATE) | [test_home/P15/](test_home/P15/) |
| P16 | COMPLETE (CANDIDATE) | [test_home/P16/](test_home/P16/) |
| P17 | COMPLETE (CANDIDATE) | [test_home/P17/](test_home/P17/) |
| P18 | COMPLETE (CANDIDATE) | [test_home/P18/](test_home/P18/) |
| P19 | COMPLETE (CANDIDATE) | [test_home/P19/](test_home/P19/) |
| P20 | COMPLETE (CANDIDATE) | [test_home/P20/](test_home/P20/) |

Every phase above has a Hard-Stop Report at `test_home/P<n>/HARD_STOP_REPORT.md`
and a passing full regression. No phase is marked beyond what the evidence
supports. [CLAIM-015]

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
| Tenant isolation | Zero cross-tenant leakage; RLS enforced | G5.2, G18.3 |

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
| Shadow | Side-by-side with live aggregate data, no committed effects | Future |
| Twin | Real-time mirror with live operational state | Future |

AminOpsTwin is currently at the **Model** stage. All data is synthetic or derived
from licensed public research aggregates. No live operational data is ingested.
The Shadow and Twin stages are future work requiring approved data sources and
additional governance.

## Measured Summary

Latest full regression: **3025 tests passed, 1 skipped, 0 failures** (P21
regression, October 2026). The full suite including all P1–P20 gates passes with
no failures. Every claim-id in this README resolves via the standalone verify CLI
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

## Hard-Stop Reports

Every phase concludes with a Hard-Stop Report stored under `test_home/P<n>/`:

| Phase | Report |
|-------|--------|
| P1 | [test_home/P1/HARD_STOP_REPORT.md](test_home/P1/HARD_STOP_REPORT.md) |
| P2 | [test_home/P2/HARD_STOP_REPORT.md](test_home/P2/HARD_STOP_REPORT.md) |
| P3 | [test_home/P3/HARD_STOP_REPORT.md](test_home/P3/HARD_STOP_REPORT.md) |
| P4 | [test_home/P4/HARD_STOP_REPORT.md](test_home/P4/HARD_STOP_REPORT.md) |
| P5 | [test_home/P5/HARD_STOP_REPORT.md](test_home/P5/HARD_STOP_REPORT.md) |
| P6 | [test_home/P6/HARD_STOP_REPORT.md](test_home/P6/HARD_STOP_REPORT.md) |
| P7 | [test_home/P7/HARD_STOP_REPORT.md](test_home/P7/HARD_STOP_REPORT.md) |
| P8 | [test_home/P8/HARD_STOP_REPORT.md](test_home/P8/HARD_STOP_REPORT.md) |
| P9 | [test_home/P9/HARD_STOP_REPORT.md](test_home/P9/HARD_STOP_REPORT.md) |
| P10 | [test_home/P10/HARD_STOP_REPORT.md](test_home/P10/HARD_STOP_REPORT.md) |
| P11 | [test_home/P11/HARD_STOP_REPORT.md](test_home/P11/HARD_STOP_REPORT.md) |
| P12 | [test_home/P12/HARD_STOP_REPORT.md](test_home/P12/HARD_STOP_REPORT.md) |
| P13 | [test_home/P13/HARD_STOP_REPORT.md](test_home/P13/HARD_STOP_REPORT.md) |
| P14 | [test_home/P14/HARD_STOP_REPORT.md](test_home/P14/HARD_STOP_REPORT.md) |
| P15 | [test_home/P15/HARD_STOP_REPORT.md](test_home/P15/HARD_STOP_REPORT.md) |
| P16 | [test_home/P16/HARD_STOP_REPORT.md](test_home/P16/HARD_STOP_REPORT.md) |
| P17 | [test_home/P17/HARD_STOP_REPORT.md](test_home/P17/HARD_STOP_REPORT.md) |
| P18 | [test_home/P18/HARD_STOP_REPORT.md](test_home/P18/HARD_STOP_REPORT.md) |
| P19 | [test_home/P19/HARD_STOP_REPORT.md](test_home/P19/HARD_STOP_REPORT.md) |
| P20 | [test_home/P20/HARD_STOP_REPORT.md](test_home/P20/HARD_STOP_REPORT.md) |

## Technology

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- PostgreSQL 16 (SQLite for offline demo)
- NetworkX (in-process graph), SimPy (discrete-event simulation)
- Hypothesis (property-based testing), mutmut (mutation testing)
- ruff (with DTZ + TID251 banned-api) + mypy --strict, import-linter
- gitleaks, pip-audit, CycloneDX (SBOM)
- uv for venv and dependency management

## Architecture

Package layout (all modules under `src/aminopstwin/`):

- `contracts/` — envelopes, schemas, reasons, Clock, IdFactory
- `gateway/` — Policy Gateway (no LLM or network imports), quota enforcement
- `executor/` — Durable Executor with checkpointing
- `agents/` — five agents (A1–A5)
- `twin/` — entities, temporal state, simulation, delta compression
- `evidence/` — registry, cache binding, impact tracking, Merkle pack, audit chain, claim graph
- `tokens/` — pre-filter, templates, budget governor, LLM adapter
- `assurance/` — weekly scheduler, zero-model assurance, signed pack, telemetry, drift detection
- `dashboard/` — views, app, wallboard, accessibility
- `enterprise/` — tenant isolation, evaluation, manifest, transparency, RLS
- `integration/` — backup, deployment, exports
- `priors/` — deterministic prior pack from public aggregates
- `ingestion/` — shadow-mode ingestion gateway (Data Contract v1)
- `shadow_pilot/` — sample Shadow Pilot report
- `fixtures_gen/` — synthetic data generator

Five agents (A1–A5), two deterministic shared services (S1 Policy Gateway, S2
Durable Executor). Every action passes through S1, then S2. [CLAIM-004] No agent
holds a direct handle to the database or the Executor store. [CLAIM-005]

## Honesty

> Honesty is a person's greatest asset, regardless of their position or work.

All claims remain Candidate until independently verified by approved evidence.
No status in this README exceeds what the evidence under `test_home/` supports.

## Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## Author

Amin Azimi | End-to-End System AI Architect | End-to-End System Development
Azimi Innovation Lab | azimilab2025@gmail.com

Project start: October 2026.

## License

Copyright 2026 Amin Azimi / Azimi Innovation Lab. All rights reserved.
Publication of this work grants no license of any kind. See [LICENSE](LICENSE).
