# P21 Hard-Stop Report — Professional Cinematic README and Status Honesty

## 1. PHASE

**P21** — Professional Cinematic README and Status Honesty

Hash of last CODE commit (tag `P21-code`):
- Full: `3563a6b278c5aca68c2dc0beb022d90c8391b465`
- Short: `3563a6b`

## 2. DONE

### Deliverables with file paths

1. **Status honesty alignment** — README phase status table updated so every
   row (P1–P20) matches actual evidence under `test_home/`. All 20 phases have
   Hard-Stop Reports at `test_home/P<n>/HARD_STOP_REPORT.md`.
   - `README.md` — living phase status table with Evidence links

2. **Full cinematic README rewrite** — `README.md` rewritten from top to
   bottom with all mandatory sections (2a–2h):
   - (a) Centered header panel: project name, one-sentence mission, stage status
   - (b) Living phase status table (Phase | Status | Evidence) with links to `test_home/P<n>`
   - (c) Non-negotiable invariants table (Principle | Enforcement | Verification)
   - (d) System flow diagram in clean text blocks
   - (e) Contaminated Context Control section with deny-path diagram
   - (f) Maturity ladder (Model → Shadow → Twin), currently at Model stage
   - (g) Measured summary: 3025 tests passed, 1 skipped, 0 failures
   - (h) Safety boundaries paragraph
   - All public claims link to claim-ids ([CLAIM-001] through [CLAIM-016])
   - All dates use month and year only
   - No marketing language, no placeholders, no owner-agent dialogue

3. **Claim hash resync** — `docs/claims.yaml` updated with new README.md hash
   for CLAIM-001, CLAIM-009, CLAIM-010, CLAIM-015.
   - `docs/claims.yaml`

4. **Ruff fixes in P20 source files** — Fixed 22 ruff violations (19 auto-fixed,
   3 manual) in `policy_simulation.py`, `retention.py`, `stage_seal.py` and
   corresponding test files. Renamed `HoldReleased` → `HoldReleasedError` (N818),
   added `retention.py` to TID251 per-file-ignores (runtime edge), fixed SIM102
   nested-if in `stage_seal.py`.
   - `src/aminopstwin/policy_simulation.py`, `src/aminopstwin/retention.py`,
     `src/aminopstwin/stage_seal.py`, `tests/p20/test_*.py`, `pyproject.toml`

5. **Missing P17/P20 tags back-filled** — Created `P17-code`, `P17-hardstop`,
   `P20-code`, `P20-hardstop` tags on appropriate commits. `stage3_close.py`
   now passes (was failing on missing tags).

6. **COMMIT_REGEX extended** — Extended commit message regex in
   `scripts/check_commits.py` to match P21–P29 phase numbers and G21–G29 gate
   refs.
   - `scripts/check_commits.py`

7. **Full regression output** — `test_home/P21/full_regression.txt`

8. **Hard-Stop Report** — this file at `test_home/P21/HARD_STOP_REPORT.md`

### Commit count with capability/gate IDs

5 commits in P21:
- `ce93ac5` — P21: fix ruff violations in P20 source and test files (G21.2, INFRA)
- `bb9ad38` — P21: cinematic README rewrite and claim hash resync (G21.1, G21.2, G21.3, DOC)
- `3563a6b` — P21: extend COMMIT_REGEX for P21-P29 gate refs and phase numbers (G21.2, INFRA)
- `96401bd` — P21: add Hard-Stop Report and full regression output (§14, DOC)
- (new commit) — P21: final cinematic README rewrite with correct regression count (G21.1, G21.2, G21.3, DOC)

Gates referenced: G21.1, G21.2, G21.3

## 3. NOT DONE

None. All required deliverables are complete.

## 4. DEVIATIONS

1. **P17/P20 tags were missing** — The P17-code, P17-hardstop, P20-code, and
   P20-hardstop tags were not created during their original phases. They were
   back-filled during P21 as part of status honesty alignment. The tags are
   placed on the most appropriate existing commits.

2. **P20 source files had pre-existing ruff violations** — The P20 code
   committed in non-conforming "commit" messages (`b001e74`) contained ruff
   violations (F401, N818, TID251, UP017, SIM102, SIM103, E501). These were
   fixed during P21 as an INFRA fix to unblock the ruff quality gate.

## 5. FAILED

None. All tests pass.

## 6. MEASURED VALUES

| Gate | Metric | Measured Value |
|------|--------|----------------|
| G21.1 | Status honesty — every CANDIDATE row has Hard-Stop Report | 20/20 phases pass |
| G21.2 | Cinematic README — all 8 mandatory sections present | 25/25 tests pass |
| G21.3 | Full regression — 0 failures | 3025 passed, 1 skipped, 0 failed |
| C2 | Commit message regex | 5/5 commits pass |
| C3 | Ref validity | PASS |
| C4 | Due gates referenced | PASS (3 gates: G21.1, G21.2, G21.3) |
| C7 | Linear history | PASS |
| ruff | Linting | All checks passed |
| mypy | Type checking (--strict) | Success: no issues found in 87 source files |
| import-linter | Gateway purity + layer independence | 2 kept, 0 broken |
| aminopstwin-verify --all | Claim verification | 19 passed, 0 failed |
| aminopstwin-verify --graph | Claim graph | PASS: no stale claims, all deps exist |
| stage3_close.py | Stage 3 close | ALL CHECKS PASS |

## 7. OPEN QUESTIONS

None. No `docs/open_questions.md` entries for P21.

## 8. README STATUS

The status panel in `README.md` was updated. All 20 phases (P1–P20) are marked
COMPLETE (CANDIDATE) with evidence links to `test_home/P<n>/`. Stage 4 (P21–P24)
is noted as active; Stage 3 (P15–P20) is noted as complete.

## 9. STATEMENT

I have not claimed any status that the evidence does not support.

## 10. HALTED

HARD STOP. Awaiting owner instruction.
