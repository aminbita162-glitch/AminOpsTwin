# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in AminOpsTwin, please report it
responsibly.

**Reporting channel:** azimilab2025@gmail.com

Please include:
- A description of the vulnerability and its potential impact.
- Steps to reproduce or a proof-of-concept.
- The affected version or commit hash.

We will acknowledge receipt within 48 hours and provide an estimated
timeline for a fix. Do not disclose the vulnerability publicly until a
fix has been released.

## Scope

This policy applies to the AminOpsTwin repository hosted at
`aminbita162-glitch/AminOpsTwin`. The project is a non-medical
operational digital twin for clinical research operations. It is not a
medical device and is not production-ready.

## Security Measures

- Deny-by-default Policy Gateway (S1) — every action passes through the
  Gateway before reaching the Executor (S2).
- No real patient or participant data is used; all data is synthetic.
- No LLM-library or network imports in the Gateway package (enforced by
  import-linter).
- Secrets scanning via gitleaks in CI.
- Dependency auditing via pip-audit in CI.
- SBOM generation via CycloneDX in CI.
