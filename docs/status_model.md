# Status Model

Three levels govern every phase and capability in AminOpsTwin:

## GOVERNANCE

Process artefacts exist: directive, gate definitions, ADRs, capability
catalog, and governance tests are in place. The phase or capability has
been specified but not yet implemented or verified.

## IMPLEMENTED

Code and tests exist and pass. The implementation matches the
specification, gates are green, and the quality bar (mypy --strict,
ruff, import-linter, full test suite) is met. This status is assigned
by the agent during development.

## VERIFIED

Set by the owner only, after independent review and green CI. No agent
and no automated process may assign this status.

## Assignment Rules

- Every capability starts at `SPECIFIED` (governance only).
- The agent may raise a capability to `IMPLEMENTED (CANDIDATE)` when
  code and tests exist and pass.
- Only the owner may raise a capability to `VERIFIED`, after
  independent review.
- A claim without code and a test behind it is a defect.
- No status exceeds what the evidence supports.
