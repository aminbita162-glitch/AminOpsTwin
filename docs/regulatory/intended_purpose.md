# Intended Purpose Record

## Operational Intended Purpose

AminOpsTwin is an operational planning tool for clinical research
operations. It models capacity, staffing, queues, scheduling,
document flow, and operational what-if scenarios using synthetic
and aggregate operational data only.

The system is designed to help research operations teams reason
about bottlenecks, capacity constraints, and resource allocation
without accessing production systems or individual-level data.

## Explicit Exclusions (Charter Clause 18)

The following are permanently out of scope and never overridable:

- **Diagnosis, prognosis, treatment, or dosing decisions** — the
  system never performs or informs any medical decision about an
  individual.
- **Patient eligibility or screening decisions** — the system does
  not assess, recommend, or influence who may participate in a
  trial.
- **Randomisation** — the system does not perform treatment
  assignment or randomisation for any study.
- **Safety-signal detection** — the system does not detect, analyse,
  or report adverse events or safety signals.
- **Adverse-event or pharmacovigilance processing** — the system
  does not process, classify, or report individual safety reports.
- **Efficacy analysis** — the system does not analyse or report
  treatment efficacy for any individual or study arm.
- **Clinical decision support** — the system provides no clinical
  decision support of any kind.
- **Individual patient data** — the system never receives, stores,
  processes, or infers data about an individual patient,
  participant, or subject, not even transiently in memory.

## Engineering Rationale

The system has no medical intended purpose because:

1. **Data boundary**: Every inbound schema rejects patient-level
   fields. Aggregation happens on the data owner's side, before
   data reaches this system. Counts below the small-cell threshold
   of 5 are suppressed.

2. **No medical model**: The simulation engine models operational
   entities — sites, staff roles, queues, visits, document flow —
   not physiological or pharmacological processes. No entity
   represents an individual patient.

3. **Operational metrics only**: All outputs are operational planning
   aids — capacity utilisation, queue lengths, cycle times, backlog
   — derived from synthetic data and public aggregate research
   material. No output is interpretable as medical advice.

4. **Non-medical boundary enforcement**: The deny-by-default Policy
   Gateway rejects any input containing patient-level data, and the
   non-medical output filter suppresses sub-threshold aggregates.
   These are protocol-level enforcement, not advisory.

5. **No clinical validation**: The system is not clinically
   validated and is not production-ready. It is a research
   operations planning tool.

This is an engineering record, not legal advice.
