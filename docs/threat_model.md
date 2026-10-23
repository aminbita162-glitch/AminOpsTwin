# threat_model.md — expanded from §11 (binding; approved at P1 Hard Stop)

## Assets

| ID   | Asset                              |
|------|------------------------------------|
| AS1  | Authoritative workflow state       |
| AS2  | Policy definitions and policy_epoch |
| AS3  | Evidence cache and registry        |
| AS4  | Audit log and evidence packs       |
| AS5  | Budget counters and transparency data |
| AS6  | Secrets and owner-held signing keys |

## Actors

| ID   | Actor                                                    |
|------|---------------------------------------------------------|
| TA1  | Malicious/malformed user input                          |
| TA2  | Malicious content inside licensed public material       |
| TA3  | Misbehaving LLM output                                  |
| TA4  | Executing-agent drift (simplification, silent skipping) |
| TA5  | Supply-chain compromise                                 |
| TA6  | Cross-tenant actor (P5+)                                |

## Threats and Controls

| ID  | Threat                           | Required Control                                      | Required Test                           |
|-----|----------------------------------|-------------------------------------------------------|-----------------------------------------|
| T01 | Direct prompt injection          | schema validation + Gateway deny + output validation | corpus INJ cases, exact codes          |
| T02 | Indirect injection via sources   | retrieved text is DATA; sanitization; evidence-span binding | poisoned-source fixtures (>=10 by P2) |
| T03 | Clinical-boundary drift          | forbidden-term AND forbidden-structure checks + output validator | corpus CLIN cases; schema field scan |
| T04 | Cache poisoning                  | bound cache key; source register; quarantine on mismatch | G2.4 tamper tests                     |
| T05 | Cache staleness after policy change | policy_epoch bump invalidates entries (§3.7)       | epoch-change test                      |
| T06 | Duplicate/replayed command       | idempotency keys, deduplication, commit intent        | duplicate-submit tests (F04)           |
| T07 | Silent state overwrite           | compare-and-swap on version; append-only history       | concurrent-write tests                 |
| T08 | LLM/agent bypass of Gateway      | Gateway in-path; no direct DB/Executor handle for agents | architecture test + import-linter     |
| T09 | Budget exhaustion abuse/race     | three-level limits; atomic reservation (§4.3)         | G2.5 tests; F09                        |
| T10 | Tenant leakage                   | tenant_id in every envelope and query; scoped access  | G5.2 tests                             |
| T11 | Secret leakage in logs/packs     | sanitized observability contract; secret scanning     | gitleaks + log-scrub tests            |
| T12 | Dependency compromise            | hash-locked lockfile; SBOM; pip-audit; request rule    | CI lock + audit check                  |
| T13 | False completion claim by agent  | independent verification (§13)                        | owner-run verify_phase.sh              |
| T14 | Timeout mistaken for success     | UNKNOWN until reconciliation (§3.6)                    | G2.3 tests; F02, F03                   |
| T15 | Principal spoofing               | no issuer field; runtime-bound principal (§3.5.1); policy matrix (§3.8) | G1.12 tests                           |
| T16 | Hash/serialization ambiguity     | restricted payload types; canonical bytes (§3.5.2)    | canonical vectors (G1.11)              |
| T17 | Commit-history manipulation      | linear history, tags, owner-run commit checker (§21)   | check_commits.py, C2-C4, C7           |
| T18 | Real identifiers in synthetic data | provenance markers; identifier-pattern scan (§23.2)  | identifier scan + canary               |

## Exclusions

Nation-state attackers and physical compromise are not claimed covered by this
engineering program; record residual risks. No regulated certification is promised.
Applicable legal duties are NOT excluded by naming them out of scope. §29 requires
a dated applicability assessment for the actual deployment.
