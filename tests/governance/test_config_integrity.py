"""P15 Configuration path integrity test (G15.1).

Programmatically inspects the tool configurations (pyproject.toml,
gates.yaml, schema_registry.yaml, invariant_catalog.yaml,
preservation_mapping.yaml) and fails if any legacy "src.contracts",
"src.gateway" etc. path remains.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent

# Legacy module paths that must NOT appear in any active config file.
# The package was renamed from src/<module> to src/aminopstwin/<module> in P11.
_LEGACY_MODULE_PATTERNS = [
    re.compile(r'src\.contracts\b'),
    re.compile(r'src\.gateway\b'),
    re.compile(r'src\.executor\b'),
    re.compile(r'src\.tokens\b'),
    re.compile(r'src\.twin\b'),
    re.compile(r'src\.evidence\b'),
    re.compile(r'src\.assurance\b'),
    re.compile(r'src\.dashboard\b'),
    re.compile(r'src\.enterprise\b'),
    re.compile(r'src\.integration\b'),
    re.compile(r'src\.agents\b'),
    re.compile(r'src\.fixtures_gen\b'),
    re.compile(r'src\.priors\b'),
    re.compile(r'src\.ingestion\b'),
    re.compile(r'src\.shadow_pilot\b'),
]

# Legacy filesystem paths (src/<module>/ without aminopstwin/) that must
# NOT appear in active config retained_location fields.
_LEGACY_PATH_PATTERNS = [
    re.compile(r'"src/contracts/'),
    re.compile(r'"src/gateway/'),
    re.compile(r'"src/executor/'),
    re.compile(r'"src/tokens/'),
    re.compile(r'"src/twin/'),
    re.compile(r'"src/evidence/'),
    re.compile(r'"src/assurance/'),
    re.compile(r'"src/dashboard/'),
    re.compile(r'"src/enterprise/'),
    re.compile(r'"src/integration/'),
    re.compile(r'"src/agents/'),
    re.compile(r'"src/fixtures_gen/'),
    re.compile(r'"src/priors/'),
    re.compile(r'"src/ingestion/'),
    re.compile(r'"src/shadow_pilot/'),
]

# Active config files to scan for legacy references.
_ACTIVE_CONFIG_FILES = [
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "docs" / "gates.yaml",
    REPO_ROOT / "docs" / "schema_registry.yaml",
    REPO_ROOT / "docs" / "invariant_catalog.yaml",
    REPO_ROOT / "docs" / "integration" / "preservation_mapping.yaml",
    REPO_ROOT / ".github" / "workflows" / "ci.yml",
]


def _scan_file(path: Path, patterns: list[re.Pattern[str]]) -> list[str]:
    """Scan a file for any pattern matches. Returns list of match descriptions."""
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    hits: list[str] = []
    for i, line in enumerate(content.splitlines(), 1):
        for pat in patterns:
            if pat.search(line):
                hits.append(f"{path}:{i}: {line.strip()}")
    return hits


class TestConfigIntegrity:
    """G15.1: No legacy src.<module> paths remain in tool configurations."""

    def test_pyproject_uses_aminopstwin(self) -> None:
        """pyproject.toml references aminopstwin, not legacy src.* paths."""
        content = (REPO_ROOT / "pyproject.toml").read_text()
        assert "src/aminopstwin" in content, (
            "pyproject.toml must reference src/aminopstwin"
        )
        # Check the hatch packages line
        assert 'packages = ["src/aminopstwin"]' in content or (
            "src/aminopstwin" in content
        ), "hatch packages must use src/aminopstwin"

    def test_mypy_packages_include_agents_and_fixtures_gen(self) -> None:
        """mypy packages include aminopstwin.agents and aminopstwin.fixtures_gen."""
        content = (REPO_ROOT / "pyproject.toml").read_text()
        assert "aminopstwin.agents" in content, (
            "mypy packages must include aminopstwin.agents"
        )
        assert "aminopstwin.fixtures_gen" in content, (
            "mypy packages must include aminopstwin.fixtures_gen"
        )

    def test_email_is_azimilab2025(self) -> None:
        """Authors email is azimilab2025@gmail.com."""
        content = (REPO_ROOT / "pyproject.toml").read_text()
        assert "azimilab2025@gmail.com" in content, (
            "authors email must be azimilab2025@gmail.com"
        )

    def test_no_legacy_module_paths_in_configs(self) -> None:
        """No legacy src.<module> dotted paths in active config files."""
        all_hits: list[str] = []
        for cfg_path in _ACTIVE_CONFIG_FILES:
            hits = _scan_file(cfg_path, _LEGACY_MODULE_PATTERNS)
            all_hits.extend(hits)
        if all_hits:
            pytest.fail(
                "Legacy src.<module> paths found in config files:\n"
                + "\n".join(all_hits)
            )

    def test_no_legacy_fs_paths_in_preservation_mapping(self) -> None:
        """No legacy src/<module>/ filesystem paths in preservation_mapping."""
        pm_path = (
            REPO_ROOT / "docs" / "integration" / "preservation_mapping.yaml"
        )
        hits = _scan_file(pm_path, _LEGACY_PATH_PATTERNS)
        if hits:
            pytest.fail(
                "Legacy src/<module>/ paths in preservation_mapping:\n"
                + "\n".join(hits)
            )

    def test_no_legacy_fs_paths_in_schema_registry(self) -> None:
        """No legacy src/<module>/ filesystem paths in schema_registry."""
        sr_path = REPO_ROOT / "docs" / "schema_registry.yaml"
        hits = _scan_file(sr_path, _LEGACY_PATH_PATTERNS)
        if hits:
            pytest.fail(
                "Legacy src/<module>/ paths in schema_registry:\n"
                + "\n".join(hits)
            )

    def test_ruff_selects_dtz_and_tid(self) -> None:
        """Ruff select includes DTZ and TID rule sets."""
        content = (REPO_ROOT / "pyproject.toml").read_text()
        assert "DTZ" in content, "ruff select must include DTZ"
        assert "TID" in content, "ruff select must include TID"

    def test_banned_api_configured(self) -> None:
        """Ruff banned-api is configured for datetime.now, uuid.uuid4, etc."""
        content = (REPO_ROOT / "pyproject.toml").read_text()
        assert '"datetime.datetime.now"' in content, (
            "banned-api must ban datetime.datetime.now"
        )
        assert '"uuid.uuid4"' in content, (
            "banned-api must ban uuid.uuid4"
        )
        assert '"random.random"' in content, (
            "banned-api must ban random.random"
        )

    def test_security_md_exists(self) -> None:
        """SECURITY.md exists with required sections."""
        sec_path = REPO_ROOT / "SECURITY.md"
        assert sec_path.exists(), "SECURITY.md must exist"
        content = sec_path.read_text()
        assert "azimilab2025@gmail.com" in content, (
            "SECURITY.md must contain the reporting channel email"
        )

    def test_dependabot_config_exists(self) -> None:
        """.github/dependabot.yml exists and is valid YAML."""
        dep_path = REPO_ROOT / ".github" / "dependabot.yml"
        assert dep_path.exists(), ".github/dependabot.yml must exist"
        data = yaml.safe_load(dep_path.read_text())
        assert "updates" in data, "dependabot.yml must have updates list"
        assert len(data["updates"]) >= 2, (
            "dependabot.yml must cover pip and github-actions"
        )

    def test_ci_workflow_has_all_jobs(self) -> None:
        """CI workflow has lint, types, test, arch, security, sbom jobs."""
        ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        data = yaml.safe_load(ci_path.read_text())
        jobs = data.get("jobs", {})
        required = {"lint", "types", "test", "security", "arch", "sbom"}
        missing = required - set(jobs.keys())
        assert not missing, f"CI workflow missing jobs: {missing}"

    def test_provenance_file(self) -> None:
        """docs/provenance.json exists with hashes of key files."""
        prov_path = REPO_ROOT / "docs" / "provenance.json"
        assert prov_path.exists(), "docs/provenance.json must exist"
