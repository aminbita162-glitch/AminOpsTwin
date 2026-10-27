"""P23 CI workflow check (G23.2).

Verifies that ``.github/workflows/ci.yml`` runs ruff, mypy --strict,
import-linter, and pytest — the four mandatory quality gates for the
supply-chain and CI baseline.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


class TestCIWorkflow:
    """G23.2: CI workflow runs ruff, mypy --strict, import-linter, and pytest."""

    def test_ci_file_exists(self) -> None:
        """``.github/workflows/ci.yml`` exists."""
        assert CI_YML.exists(), ".github/workflows/ci.yml must exist"

    def test_ci_runs_ruff(self) -> None:
        """CI workflow includes a ruff check step."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        assert "ruff" in content, "CI workflow must run ruff check"

    def test_ci_runs_mypy_strict(self) -> None:
        """CI workflow includes a mypy --strict step."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        assert "mypy" in content, "CI workflow must run mypy"
        assert "--strict" in content, (
            "CI workflow must run mypy with --strict"
        )

    def test_ci_runs_import_linter(self) -> None:
        """CI workflow includes an import-linter step."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        assert "import-linter" in content or "lint-imports" in content, (
            "CI workflow must run import-linter (lint-imports)"
        )

    def test_ci_runs_pytest(self) -> None:
        """CI workflow includes a pytest step."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        assert "pytest" in content, "CI workflow must run pytest"

    def test_ci_permissions_read_only(self) -> None:
        """CI workflow uses ``permissions: contents: read``."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        assert "contents: read" in content, (
            "CI workflow must set permissions: contents: read"
        )

    def test_ci_actions_pinned_by_sha(self) -> None:
        """CI workflow pins GitHub Actions by SHA, not floating tag."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        # Every actions/checkout or actions/setup-python must use a SHA
        # (40-char hex), not a bare version tag like @v4.
        import re

        uses_pattern = re.compile(r"uses:\s*(\S+)", re.MULTILINE)
        for match in uses_pattern.finditer(content):
            ref = match.group(1)
            # Skip third-party actions that may use version tags
            # (e.g., gitleaks/gitleaks-action)
            if ref.startswith("actions/"):
                # Must be pinned by SHA (40 hex chars after @)
                at_pos = ref.rfind("@")
                if at_pos == -1:
                    continue
                sha = ref[at_pos + 1:]
                assert len(sha) >= 40, (
                    f"GitHub Action {ref} must be pinned by SHA, "
                    f"not floating tag (got {sha!r})"
                )
                assert re.match(r"^[0-9a-f]{40}$", sha), (
                    f"GitHub Action {ref} SHA must be 40 hex chars "
                    f"(got {sha!r})"
                )
