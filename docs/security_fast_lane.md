# Security Fast-Lane Process for Patch-Level Updates

## Scope

This document defines the fast-lane process for applying **patch-level**
security updates to AminOpsTwin dependencies. A patch-level update is a
dependency version change where only the patch component (the third
number in `major.minor.patch`) increases — e.g., `1.2.3` → `1.2.4`.

Major or minor version bumps are NOT covered by this fast-lane. They
require the full review process: running the complete test suite
locally, manual code review of any API changes, and explicit owner
approval before merge.

## What Qualifies as a Patch-Level Security Update

1. A Dependabot PR that bumps a dependency by a patch version only
   (`X.Y.Z` → `X.Y.Z+1`).
2. The PR contains no code changes other than `pyproject.toml` and
   `uv.lock`.
3. The dependency is not a breaking-change release (no major or minor
   version increase).

## Fast-Lane Steps

1. **Verify the PR is patch-level only.** Run `gh pr diff <number>` and
   confirm only `pyproject.toml` and `uv.lock` changed, and that the
   version bump is patch-only (third number increases).

2. **Run `uv lock --check` locally.** After applying the PR changes,
   verify the lockfile is consistent:
   ```bash
   uv lock --check
   ```

3. **Run `pip-audit --strict`.** Verify the new version has no known
   high or critical vulnerabilities:
   ```bash
   .venv/bin/python -m pip_audit --strict
   ```

4. **Run gitleaks scan.** Confirm no secrets were introduced:
   ```bash
   gitleaks detect --source . --no-banner
   ```

5. **Run the test suite.** Verify all tests pass with the updated
   dependency:
   ```bash
   PYTHONHASHSEED=0 .venv/bin/python -m pytest -q --tb=short --no-header --no-cov
   ```

6. **Run `uv lock` to refresh the lockfile.** If the PR did not
   include an updated `uv.lock`, regenerate it:
   ```bash
   uv lock
   ```
   Then commit the refreshed lockfile.

7. **Squash-merge the PR.** Dependabot PRs create merge commits by
   default; use `gh pr merge --squash` to maintain linear history (§21.2
   of the directive prohibits merge commits).

8. **Record the update.** Log the patch-level update in the commit
   message with the `INFRA` ref tag:
   ```
   P23: apply patch-level security update to <package> (INFRA)
   ```

## What Does NOT Qualify

- **Major version bumps** (e.g., `1.2.3` → `2.0.0`): require full
  review and explicit owner approval.
- **Minor version bumps** (e.g., `1.2.3` → `1.3.0`): require full
  review and explicit owner approval.
- **GitHub Actions version bumps**: CI actions are pinned by SHA;
  the new SHA must be owner-verified before merge.
- **Any PR that includes code changes** beyond `pyproject.toml` and
  `uv.lock`: requires full review.

## CI Enforcement

The CI workflow (`.github/workflows/ci.yml`) enforces the following
supply-chain gates on every push and pull request:

- **ruff** — linting
- **mypy --strict** — type checking
- **import-linter** — architecture boundaries (Gateway purity)
- **pytest** — full test suite
- **uv lock --check** — lockfile freshness
- **gitleaks** — secrets scanning
- **pip-audit** — dependency vulnerability audit

A patch-level update that passes all CI gates is safe to merge. If any
gate fails, the update does not qualify for the fast-lane and requires
manual investigation.
