# ADR-001: Hash-locked lockfile (uv.lock)

## Status

Accepted

## Context

Stage 2 (P11) requires a hash-locked dependency file to ensure reproducible
installs across environments. The project uses `uv` for virtual environment
and dependency management.

## Decision

Use `uv lock` to generate and commit `uv.lock` as the project's hash-locked
lockfile. Add a CI check (`uv lock --check`) to verify the lockfile is
up to date on every push.

`uv.lock` pins exact package versions and hashes for all dependencies
and dev dependencies. `uv pip install -e ".[dev]"` resolves against
this lockfile when it is present, ensuring every environment installs
the same versions.

## Alternatives considered

- **pip-compile / requirements.txt with hashes**: Requires a separate
  tool and workflow. `uv` is already the project's package manager;
  using its native lockfile avoids an additional tool.
- **No lockfile**: Risks dependency drift between development, CI, and
  deployment environments. A hash-locked file is required by the P11
  directive.

## Consequences

- `uv lock` must be re-run whenever `pyproject.toml` dependencies change.
- CI fails if the lockfile is out of date, catching uncommitted changes.
- The lockfile is ~180 KB and tracks 102 packages; it is committed to
  the repository and updated on dependency changes.
