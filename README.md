# AminOpsTwin — Operational Cognitive Digital Twin for Clinical Research Operations

## STATUS: CANDIDATE

All claims remain Candidate until independently verified by owner-approved evidence.

Stage 3 (P15–P20) is active. P1 through P14 are COMPLETE (CANDIDATE).

### What it is

AminOpsTwin is a non-medical **operational** cognitive digital twin for clinical
**research operations** — capacity planning, queues, scheduling, bottleneck
analysis, and operational "what-if" scenarios. [CLAIM-001] It uses synthetic
operational data and licensed public research material only. [CLAIM-003] It is
**not** a medical device, does not perform diagnosis, prognosis, treatment, or
dose recommendation, and never models individual patient state. [CLAIM-006]

### What it is not

- Not a medical decision system (§2.2) [CLAIM-006]
- Not clinically validated (§0.3) [CLAIM-009]
- Not production-ready (§0.3) [CLAIM-009]
- Not synchronized with a real organization (§1) [CLAIM-010]
- Does not use real patient or participant data (§2.5) [CLAIM-008]

### Architecture

```
                    ┌──────────────────┐
   A1..A5 ────────►│  Policy Gateway   │── ALLOW ──► S2 Executor ──► committed effect
   (agents)        │  (S1) deny-by-    │
                    │  default          │── DENY ────► reason code + log
                    └──────────────────┘
                         ▲
                    schema | epoch | auth | invariant | budget
                    (pre-filter)
```

Package layout (all modules under `src/aminopstwin/`):

- `contracts/` — envelopes, schemas, reasons, Clock, IdFactory
- `gateway/` — Policy Gateway (no LLM or network imports)
- `executor/` — Durable Executor with checkpointing
- `agents/` — five agents (A1–A5)
- `twin/` — entities, temporal state, simulation, delta compression
- `evidence/` — registry, cache binding, impact tracking
- `tokens/` — pre-filter, templates, budget governor, LLM adapter
- `assurance/` — weekly scheduler, zero-model assurance
- `dashboard/` — views, app, wallboard, accessibility
- `enterprise/` — tenant isolation, evaluation, manifest, transparency
- `integration/` — backup, deployment, exports
- `priors/` — deterministic prior pack from public aggregates
- `ingestion/` — shadow-mode ingestion gateway (Data Contract v1)
- `shadow_pilot/` — sample Shadow Pilot report
- `fixtures_gen/` — synthetic data generator

Five agents (A1-A5), two deterministic shared services (S1 Policy Gateway, S2
Durable Executor). Every action passes through S1, then S2. [CLAIM-004] No
agent holds a direct handle to the database or the Executor store (§3.3).
[CLAIM-005]

### Honesty

> Honesty is a person's greatest asset, regardless of their position or work.

### Technology

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- PostgreSQL 16 (SQLite for offline demo)
- NetworkX (in-process graph), SimPy (discrete-event simulation)
- Hypothesis (property-based testing), mutmut (mutation testing)
- ruff (with DTZ + TID251 banned-api) + mypy --strict, import-linter
- gitleaks, pip-audit, CycloneDX (SBOM)
- uv for venv and dependency management

### Phase status

| Phase | Description | Status |
|-------|-------------|--------|
| P1 | Foundation and Governance | COMPLETE (CANDIDATE) |
| P2 | Runtime Core and Evidence | COMPLETE (CANDIDATE) |
| P3 | Twin and Operational Simulation | COMPLETE (CANDIDATE) |
| P4 | Governed Knowledge and Memory | COMPLETE (CANDIDATE) |
| P5 | Operational Intelligence Capabilities | COMPLETE (CANDIDATE) |
| P6 | Assurance Interface and Weekly Checks | COMPLETE (CANDIDATE) |
| P7 | Responsive Dashboard and User Interface | COMPLETE (CANDIDATE) |
| P8 | Enterprise Hardening and Evaluation | COMPLETE (CANDIDATE) |
| P9 | Integration, Exports and Pre-Release | COMPLETE (CANDIDATE) |
| P10 | Final Verification, README, Release | COMPLETE (CANDIDATE) |
| P11 | Spec Consolidation, Package Hygiene | COMPLETE (CANDIDATE) |
| P12 | Core Determinism and Safety Hardening | COMPLETE (CANDIDATE) |
| P13 | Evidence Infrastructure, Prior Pack, Shadow Ingestion | COMPLETE (CANDIDATE) |
| P14 | Shadow Pilot Readiness, Claim Verification, Stage 2 Close | COMPLETE (CANDIDATE) |
| P15 | Absolute Integrity, Toolchain and Professional Surface | COMPLETE (CANDIDATE) |
| P16 | Bit-Reproducible Deterministic Substrate | COMPLETE (CANDIDATE) |
| P17–P20 | Stage 3 phases | NOT STARTED |

### Stage 3 (P15–P20) — Active

Stage 3 is active. P1 through P14 are COMPLETE (CANDIDATE). Stage 2 is no
longer the active stage — Stage 3 (P15–P20) is the current development
sequence.

### Hard-Stop Reports

- P11: [test_home/P11/HARD_STOP_REPORT.md](test_home/P11/HARD_STOP_REPORT.md)
- P12: [test_home/P12/HARD_STOP_REPORT.md](test_home/P12/HARD_STOP_REPORT.md)
- P13: [test_home/P13/HARD_STOP_REPORT.md](test_home/P13/HARD_STOP_REPORT.md)
- P14: [test_home/P14/HARD_STOP_REPORT.md](test_home/P14/HARD_STOP_REPORT.md)
- P15: [test_home/P15/HARD_STOP_REPORT.md](test_home/P15/HARD_STOP_REPORT.md)
- P16: [test_home/P16/HARD_STOP_REPORT.md](test_home/P16/HARD_STOP_REPORT.md)

### Measured summary

Latest full-suite run: 2647 tests passed, 3 skipped, 0 failures (P16
regression). The full suite including all P1–P16 gates passes with no
failures.

### Security

See [SECURITY.md](SECURITY.md) for vulnerability reporting.

### Author

Amin Azimi | End-to-End System AI Architect | End-to-End System Development |
Azimi Innovation Lab | azimilab2025@gmail.com

Project start: October 2026.

### License

Copyright 2026 Amin Azimi / Azimi Innovation Lab. All rights reserved.
Publication of this work grants no license of any kind. See [LICENSE](LICENSE).
