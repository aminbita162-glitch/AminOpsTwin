# P22 Hard-Stop Report — Directive Consistency and Governance Cleanup

## 1. PHASE

**P22** — Directive Consistency and Governance Cleanup

Hash of last CODE commit (tag `P22-code`):
- Full: `5cb1c5fa92d8c37be8f38648c4b1b1d61d22ea5a`
- Short: `5cb1c5f`

## 2. DONE

### Deliverables with file paths

1. **Remove internal contradictions in directive.txt** — Verified that
   directive.txt has a single active phase sequence (P21–P24), a single
   status vocabulary (EXECUTION CANDIDATE / COMPLETE (CANDIDATE)), and
   no outdated phase references (no "Stage 1/2/3 active", no
   "P1–P10 active", etc.).
   - `directive.txt` — already clean (no contradictions found)
   - `scripts/check_directive_consistency.py` — 6-check consistency script
   - `tests/p22/test_directive_consistency.py` — 7 tests (G22.1)

2. **Eliminate remaining OWNER-FILL or outdated phase references** —
   Verified that directive.txt contains no bracketed `[OWNER-FILL]`
   placeholder values. The bare word "OWNER-FILL" appears legitimately
   in rule sentences (lines 22, 81) as meta-references to the concept,
   not unfilled values. No outdated phase references remain in
   directive.txt, gates.yaml, or check_commits.py.
   - `tests/p22/test_owner_fill_eliminated.py` — 5 tests (G22.2)

3. **Ensure gates.yaml is the single source for gate identifiers** —
   Verified that check_commits.py GATE_IDS (128 IDs) exactly matches
   gates.yaml gate IDs (128 IDs). No drift, no extras, no missing.
   PHASE_GATES references only IDs present in GATE_IDS. COMMIT_REGEX
   supports P22 phase numbers and G22 gate refs.
   - `docs/gates.yaml` — G22.1–G22.4 added (single source for gate IDs)
   - `scripts/check_commits.py` — G22.1–G22.4 added to GATE_IDS and
     PHASE_GATES["P22"]
   - `tests/p22/test_gate_source_consistency.py` — 5 tests (G22.3)

4. **Acceptance: consistency check confirms no conflicting phase
   sequences or status terms remain** —
   `scripts/check_directive_consistency.py` passes all 6 checks:
   - Single active phase sequence: P21–P24
   - Single status vocabulary: COMPLETE (CANDIDATE)
   - No outdated phase references
   - No [OWNER-FILL] placeholders in directive.txt
   - gates.yaml matches check_commits.py GATE_IDS
   - README status matches evidence under test_home/

5. **Full regression** — 3042 passed, 1 skipped, 0 failures.
   - `test_home/P22/full_regression.txt`
   - `tests/p22/test_regression.py` — 1 test (G22.4)

6. **P21 regression test updated** — Added `--ignore tests/p22/test_regression.py`
   and `AMINOPS_REGRESSION_NESTED_P22=1` env var to prevent nested
   recursion when P22's regression runs the full suite.
   - `tests/p21/test_regression.py`

7. **README measured summary updated** — Updated from "3025 tests passed
   (P21 regression)" to "3042 tests passed (P22 regression)". Resynced
   4 README.md claim hashes in `docs/claims.yaml`.
   - `README.md`, `docs/claims.yaml`

### Dependabot PR Review (10 open PRs — ALL DEFERRED)

| PR | Title | Type | Status | Reason |
|----|-------|------|--------|--------|
| #1 | Bump gitleaks/gitleaks-action SHA | GitHub Action SHA bump | DEFERRED | New SHA must be owner-verified; merge commit violates §21.2 (linear history) |
| #2 | Update pytest `<9.0.0`→`<10.0.0` | Version range widening | DEFERRED | Constraint relaxation only; lockfile pins working version; merge commit violates §21.2 |
| #3 | Bump actions/setup-python 5.6.0→7.1.0 | GitHub Action major bump | DEFERRED | Major version bump; new SHA must be owner-verified; merge commit violates §21.2 |
| #4 | Update mypy `<2.0.0`→`<3.0.0` | Version range widening | DEFERRED | Constraint relaxation only; merge commit violates §21.2 |
| #5 | Bump actions/checkout 4.4.0→7.0.1 | GitHub Action major bump | DEFERRED | Major version bump; new SHA must be owner-verified; merge commit violates §21.2 |
| #6 | Update mutmut `<3.0.0`→`<4.0.0` | Version range widening | DEFERRED | Constraint relaxation only; merge commit violates §21.2 |
| #7 | Update pytest-cov `<6.0.0`→`<8.0.0` | Version range widening | DEFERRED | Constraint relaxation only; merge commit violates §21.2 |
| #8 | Update schemathesis `<4.0.0`→`<5.0.0` | Major version range | DEFERRED | Major version range; merge commit violates §21.2 |
| #9 | Update fastapi `<0.116.0`→`<0.160.0` | Major version range | DEFERRED | Major version range; merge commit violates §21.2 |
| #10 | Update cyclonedx-bom `<5.0.0`→`<8.0.0` | Major version range | DEFERRED | Major version range; merge commit violates §21.2 |

**Total open PRs: 10. Deferred: 10. Merged: 0.**

Per the Dependabot PR Procedure in the aminopstwin-directives skill:
- All Dependabot PRs create merge commits, which violate §21.2 (linear
  history only, no merge commits).
- Version-range widenings change only pyproject.toml constraints; the
  lockfile already pins the working version, so merging changes nothing
  at runtime.
- GitHub Actions SHA bumps require owner verification of the new SHA.
- All PRs are deferred until the owner explicitly authorizes merging in
  a foreground session.

### Commit count with capability/gate IDs

4 commits in P22:
- `ce78a5d` — P22: add G22 gate IDs, phase gates, and gates.yaml entries for directive consistency (G22.1, G22.2, G22.3, G22.4, INFRA)
- `479790e` — P22: add consistency check script and directive governance tests (G22.1, G22.2, G22.3, INFRA)
- `4c8b87f` — P22: update P21 regression to ignore P22 nested regression test (G22.4, INFRA)
- `5cb1c5f` — P22: update README measured summary and resync claim hashes (G22.1, G22.2, G22.3, DOC)

Gates referenced: G22.1, G22.2, G22.3, G22.4

## 3. NOT DONE

None. All required deliverables are complete.

## 4. DEVIATIONS

1. **Non-conforming commit `110d1ae`** — The commit "Update token_baseline.json"
   (`110d1ae`) was auto-generated by a prior session's test run and pushed to
   origin/main. It does not follow the §21.3 commit-message format (no `PN:`
   prefix). Per §21.2, this cannot be amended or force-pushed away. It is
   recorded as a deviation; the `P22-code` tag is placed on the last conforming
   code commit (`5cb1c5f`), not on the non-conforming commit.

2. **Directive.txt was already clean** — The P22 directive's deliverable 1
   ("Remove internal contradictions in directive.txt") found no
   contradictions to remove. The directive already had a single active phase
   sequence (P21–P24), a single status vocabulary (EXECUTION CANDIDATE), and
   no outdated phase references. The consistency check script and tests
   verify this state is maintained going forward.

## 5. FAILED

None. All tests pass.

## 6. MEASURED VALUES

| Gate | Metric | Measured Value |
|------|--------|----------------|
| G22.1 | Directive consistency — single phase sequence, single status vocabulary | 7/7 tests pass |
| G22.2 | No remaining OWNER-FILL or outdated phase references | 5/5 tests pass |
| G22.3 | gates.yaml is single source for gate identifiers | 5/5 tests pass |
| G22.4 | Full regression 0 failures | 3042 passed, 1 skipped, 0 failed |
| C2 | Commit message regex | 4/4 commits pass |
| C3 | Ref validity | PASS |
| C4 | Due gates referenced | PASS (4 gates: G22.1, G22.2, G22.3, G22.4) |
| C7 | Linear history | PASS |
| ruff | Linting (src/aminopstwin/ tests/) | All checks passed |
| mypy | Type checking (--strict, 87 source files) | Success: no issues found |
| import-linter | Gateway purity + layer independence | 2 kept, 0 broken |
| aminopstwin-verify --all | Claim verification | 19 passed, 0 failed |
| aminopstwin-verify --graph | Claim graph | PASS: no stale claims, all deps exist |
| check_directive_consistency.py | Consistency check script | PASS (all 6 checks) |

## 7. OPEN QUESTIONS

None. No `docs/open_questions.md` entries for P22.

## 8. README STATUS

The status panel in `README.md` was updated. The measured summary now
reads "3042 tests passed, 1 skipped, 0 failures (P22 regression, October
2026)". Stage 4 (P21–P24) remains active; P1–P20 remain COMPLETE (CANDIDATE).
All 19 claims in `docs/claims.yaml` pass verification with the resynced
README.md hash.

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction.
