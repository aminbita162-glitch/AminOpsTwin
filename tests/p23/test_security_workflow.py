"""P23 security workflow check (G23.3).

Verifies that CI includes a security workflow that runs gitleaks
and pip-audit (or equivalent tools). The security jobs may be in
``ci.yml`` or in a separate workflow file under ``.github/workflows/``.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


class TestSecurityWorkflow:
    """G23.3: security workflow runs gitleaks and pip-audit."""

    def test_gitleaks_in_ci(self) -> None:
        """CI includes a gitleaks secrets scanning step."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        assert "gitleaks" in content, (
            "CI workflow must run gitleaks for secrets scanning"
        )

    def test_pip_audit_in_ci(self) -> None:
        """CI includes a pip-audit dependency audit step."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        assert "pip-audit" in content, (
            "CI workflow must run pip-audit for dependency auditing"
        )

    def test_security_job_exists(self) -> None:
        """CI has a dedicated security job."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        # The security job should be present
        assert "security" in content, (
            "CI workflow must have a security job"
        )

    def test_dependabot_configured(self) -> None:
        """Dependabot is configured for pip and github-actions ecosystems."""
        dependabot = REPO_ROOT / ".github" / "dependabot.yml"
        assert dependabot.exists(), ".github/dependabot.yml must exist"
        content = dependabot.read_text()
        assert "pip" in content, (
            "Dependabot must monitor pip ecosystem"
        )
        assert "github-actions" in content, (
            "Dependabot must monitor github-actions ecosystem"
        )

    def test_security_md_exists(self) -> None:
        """SECURITY.md exists for vulnerability reporting."""
        security_md = REPO_ROOT / "SECURITY.md"
        assert security_md.exists(), "SECURITY.md must exist"
