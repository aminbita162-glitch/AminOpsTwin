# ADR-002: Licence — comprehensive reservation of rights

## Status

Accepted

## Context

The project contains proprietary work by the owner. The licence must
express every right the owner reserves, covering use, sale, assignment,
licensing, derivative works, sublicensing, and relicensing. The licence
file (LICENSE) must state plainly that it is an engineering reservation
of rights, not legal advice.

## Decision

All rights are reserved by the owner. The owner alone may, at any time
and in any combination:

- use;
- gift;
- sell;
- assign the whole work or any individual module;
- grant exclusive or non-exclusive, perpetual or term, field-limited or
  territory-limited licences;
- authorise or create derivative works;
- sublicense; and
- relicense, including under open-source or commercial terms.

Publication grants no rights. Third-party components keep their own
licences.

The LICENSE file is rewritten to express every one of these rights
explicitly, and it retains the line stating that it is an engineering
reservation of rights, not legal advice.

## Consequences

- The LICENSE file is the authoritative expression of the reservation
  of rights.
- Third-party components remain under their own licences; this ADR does
  not alter them.
- No licence is granted by publication or distribution alone.

## Proof tests

- `tests/governance/test_adr_schema.py` — verifies each ADR has status
  Accepted, deciders, and date.
- `tests/docs/test_licence_claims.py` — verifies the LICENSE file
  contains the required reservation-of-rights sentences.
