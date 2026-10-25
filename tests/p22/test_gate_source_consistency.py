"""P22 gate source consistency test (G22.3).

Verifies that gates.yaml is the single source of truth for gate
identifiers. The check_commits.py GATE_IDS set must exactly match
the gate IDs defined in gates.yaml — no drift, no extras, no missing.
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
        """check_commits.py GATE_IDS exactly matches gates.yaml gate IDs."""
        yaml_text = GATES_YAML.read_text()
        yaml_ids = set(re.findall(r"G\d+\.\d+", yaml_text))
        yaml_ids |= {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9"}

        cc_text = CHECK_COMMITS.read_text()
        m = re.search(r"GATE_IDS\s*=\s*\{([^}]+)\}", cc_text)
        assert m is not None, "GATE_IDS set not found in check_commits.py"
        code_ids = set(re.findall(r'"([^"]+)"', m.group(1)))

        assert yaml_ids == code_ids, (
            f"Gate ID mismatch:\n"
            f"  In gates.yaml but NOT in check_commits.py: "
            f"{sorted(yaml_ids - code_ids)}\n"
            f"  In check_commits.py but NOT in gates.yaml: "
            f"{sorted(code_ids - yaml_ids)}"
        )

    def test_phase_gates_match_yaml(self) -> None:
        """PHASE_GATES in check_commits.py only references gates in GATE_IDS."""
        cc_text = CHECK_COMMITS.read_text()
        m_ids = re.search(r"GATE_IDS\s*=\s*\{([^}]+)\}", cc_text)
        assert m_ids is not None
        gate_ids = set(re.findall(r'"([^"]+)"', m_ids.group(1)))

        m_phase = re.search(r"PHASE_GATES\s*=\s*\{(.+?)\n\}", cc_text, re.DOTALL)
        assert m_phase is not None, "PHASE_GATES dict not found"
        phase_gate_text = m_phase.group(1)
        referenced_ids = set(re.findall(r'"(G\d+\.\d+)"', phase_gate_text))

        unknown = referenced_ids - gate_ids
        assert not unknown, (
            f"PHASE_GATES references gate IDs not in GATE_IDS: {sorted(unknown)}"
        )

    def test_commit_regex_supports_p22(self) -> None:
        """COMMIT_REGEX supports P22 phase numbers and G22 gate refs."""
        cc_text = CHECK_COMMITS.read_text()
        m = re.search(r"COMMIT_REGEX\s*=\s*re\.compile\((.+?)\)", cc_text, re.DOTALL)
        assert m is not None, "COMMIT_REGEX not found"
        regex_str = m.group(1)
        # Must support P22 (phase number 22)
        assert "2[0-9]" in regex_str, (
            "COMMIT_REGEX must support phase numbers P20-P29"
        )
