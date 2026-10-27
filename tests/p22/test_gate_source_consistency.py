"""P22 gate source consistency test (G22.3, updated for P25).

Verifies that gates.yaml is the single source of truth for gate
identifiers. After P25, check_commits.py loads gate IDs from
gates.yaml dynamically. This test verifies that the dynamic loading
produces the same set as the gates.yaml file, and that the commit
regex supports all phases up to P99.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
GATES_YAML = REPO_ROOT / "docs" / "gates.yaml"
CHECK_COMMITS = REPO_ROOT / "scripts" / "check_commits.py"


class TestGateSourceConsistency:
    """G22.3: gates.yaml is the single source for gate identifiers."""

    def test_gates_yaml_exists(self) -> None:
        assert GATES_YAML.exists(), "docs/gates.yaml must exist"

    def test_check_commits_exists(self) -> None:
        assert CHECK_COMMITS.exists(), "scripts/check_commits.py must exist"

    def test_gate_ids_match(self) -> None:
        """check_commits.py loads the same gate IDs as gates.yaml."""
        yaml_text = GATES_YAML.read_text()
        yaml_ids: set[str] = set()
        for m in re.finditer(
            r'^\s+-\s+id:\s*"?(G\d+\.\d+)"?', yaml_text, re.MULTILINE
        ):
            yaml_ids.add(m.group(1))
        for m in re.finditer(
            r'^\s+-\s+id:\s*"?(C\d+)"?', yaml_text, re.MULTILINE
        ):
            yaml_ids.add(m.group(1))

        # check_commits.py should load gate IDs from gates.yaml
        cc_text = CHECK_COMMITS.read_text()
        assert "_load_gate_ids_from_yaml" in cc_text, (
            "check_commits.py must load gate IDs from gates.yaml"
        )
        # Import the module and check the loaded set
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_commits", CHECK_COMMITS
        )
        if spec is None or spec.loader is None:
            raise AssertionError("Cannot load check_commits.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        code_ids = mod.GATE_IDS

        assert yaml_ids == code_ids, (
            f"Gate ID mismatch:\n"
            f"  In gates.yaml but NOT in check_commits.py: "
            f"{sorted(yaml_ids - code_ids)}\n"
            f"  In check_commits.py but NOT in gates.yaml: "
            f"{sorted(code_ids - yaml_ids)}"
        )

    def test_phase_gates_match_yaml(self) -> None:
        """PHASE_GATES in check_commits.py references only gates in GATE_IDS."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_commits_cc", CHECK_COMMITS
        )
        if spec is None or spec.loader is None:
            raise AssertionError("Cannot load check_commits.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        for _phase, gates in mod.PHASE_GATES.items():
            unknown = gates - mod.GATE_IDS
            assert not unknown, (
                f"PHASE_GATES[{_phase}] references gate IDs not in GATE_IDS: "
                f"{sorted(unknown)}"
            )

    def test_commit_regex_supports_p99(self) -> None:
        """COMMIT_REGEX supports phase numbers P1 through P99."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "check_commits_cr", CHECK_COMMITS
        )
        if spec is None or spec.loader is None:
            raise AssertionError("Cannot load check_commits.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # Test that P1 through P99 are all valid
        for i in range(1, 100):
            test_msg = f"P{i}: summary message here (INFRA)"
            assert mod.COMMIT_REGEX.match(test_msg), (
                f"COMMIT_REGEX must support phase P{i}"
            )
