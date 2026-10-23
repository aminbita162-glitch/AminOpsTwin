# AminOpsTwin — Operational Cognitive Digital Twin for Clinical Research Operations

## STATUS: CANDIDATE

All claims remain Candidate until independently verified by owner-approved evidence.

### What it is

AminOpsTwin is a non-medical **operational** cognitive digital twin for clinical
**research operations** — capacity planning, queues, scheduling, bottleneck
analysis, and operational "what-if" scenarios. It uses synthetic operational data
and licensed public research material only. It is **not** a medical device, does
not perform diagnosis, prognosis, treatment, or dose recommendation, and never
models individual patient state.

### What it is not

- Not a medical decision system (§2.2)
- Not clinically validated (§0.3)
- Not production-ready (§0.3)
- Not synchronized with a real organization (§1)
- Does not use real patient or participant data (§2.5)

### Architecture (P1 foundation)

```
                    ┌──────────────┐
   A1..A5 ────────►│  Policy      │── ALLOW ──► S2 Executor ──► committed effect
   (agents)        │  Gateway (S1) │
                    │  deny-by-    │── DENY ────► reason code + log
                    │  default     │
                    └──────────────┘
                         ▲
                    schema | epoch | auth | invariant | budget
                    (pre-filter, §4.1)
```

Five agents (A1-A5), two deterministic shared services (S1 Policy Gateway, S2
Durable Executor). Every action passes through S1, then S2. No agent holds a
direct handle to the database or the Executor store (§3.3).

### Honesty

> Honesty is a person's greatest asset, regardless of their position or work.

### Technology

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic
- PostgreSQL 16 (SQLite for offline demo)
- NetworkX (in-process graph), SimPy (discrete-event simulation)
- Hypothesis (property-based testing), mutmut (mutation testing)
- ruff + mypy --strict, import-linter, gitleaks, pip-audit

### Phase status

| Phase | Description                          | Status      |
|-------|--------------------------------------|-------------|
| P1    | Foundation and Governance           | COMPLETE (CANDIDATE) |
| P2    | Runtime Core and Evidence            | COMPLETE (CANDIDATE) |
| P3    | Twin and Operational Simulation      | COMPLETE (CANDIDATE) |
| P4    | Governed Knowledge and Memory       | COMPLETE (CANDIDATE) |
| P5    | Operational Intelligence Capabilities | COMPLETE (CANDIDATE) |
| P6    | Assurance Interface and Weekly Checks | COMPLETE (CANDIDATE) |
| P7    | Responsive Dashboard and User Interface | NOT STARTED |
| P8    | Enterprise Hardening and Evaluation | NOT STARTED |
| P9    | Integration, Exports and Pre-Release | NOT STARTED |
| P10   | Final Verification, README, Release  | NOT STARTED |

### Author

Amin Azimi | End-to-End System AI Architect | End-to-End System Development |
Business Challenge | Azimi Innovation Lab

Project start: October 2026.

### License

Copyright 2026 Amin Azimi / Azimi Innovation Lab. All rights reserved.
Publication of this work grants no license of any kind. See [LICENSE](LICENSE).
