"""Unit tests for check_commits.py (P25 deliverable 1).

Tests cover valid messages, invalid messages, and every boundary case
for the generalised commit-message regex and the YAML-based gate loading.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent.parent
_CHECK_COMMITS = _REPO_ROOT / "scripts" / "check_commits.py"

spec = importlib.util.spec_from_file_location("check_commits", _CHECK_COMMITS)
if spec is None or spec.loader is None:
    raise RuntimeError("Cannot load check_commits.py")
_cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_cc)

COMMIT_REGEX = _cc.COMMIT_REGEX
GATE_IDS = _cc.GATE_IDS
CAPABILITY_IDS = _cc.CAPABILITY_IDS
ALL_VALID_REFS = _cc.ALL_VALID_REFS
PHASE_GATES = _cc.PHASE_GATES


class TestCommitRegex:
    """C2 regex: valid and invalid commit messages."""

    @pytest.mark.parametrize(
        "msg",
        [
            "P1: add gateway module (G1.1, INFRA)",
            "P9: add export bundle signing (G6.1, G6.2, §3.5)",
            "P10: final regression and release notes (G6.6, G6.7, DOC)",
            "P24: add stage seal and final verification (G24.1, INFRA)",
            "P25: register P25 gates in gates.yaml (G25.1, G25.2, G25.3, G25.4, G25.5, G25.6, G25.7, G25.8, INFRA)",
            "P99: final phase delivery (R01, N01, INFRA)",
            "P5: add experiment designer (G4.7, G4.8, G4.9)",
        ],
    )
    def test_valid_messages(self, msg: str) -> None:
        assert COMMIT_REGEX.match(msg), f"Should match: {msg}"

    @pytest.mark.parametrize(
        "msg",
        [
            "P0: invalid phase zero (INFRA)",
            "P100: phase too large (INFRA)",
            "P1: missing refs ()",
            "P1: no parens",
            "P1: too long summary " + "x" * 100 + " (INFRA)",
            "P1: invalid ref (Z99)",
            "P1: missing closing paren (INFRA",
            "not a commit message at all",
            "P1: empty summary ()",
            "P-1: negative phase (INFRA)",
        ],
    )
    def test_invalid_messages(self, msg: str) -> None:
        assert not COMMIT_REGEX.match(msg), f"Should NOT match: {msg}"

    def test_boundary_phase_1(self) -> None:
        assert COMMIT_REGEX.match("P1: boundary test (INFRA)")

    def test_boundary_phase_99(self) -> None:
        assert COMMIT_REGEX.match("P99: boundary test (INFRA)")

    def test_boundary_summary_8_chars(self) -> None:
        assert COMMIT_REGEX.match("P1: 12345678 (INFRA)")

    def test_boundary_summary_100_chars(self) -> None:
        summary = "x" * 100
        msg = f"P1: {summary} (INFRA)"
        assert COMMIT_REGEX.match(msg)

    def test_boundary_summary_too_short(self) -> None:
        msg = "P1: 1234567 (INFRA)"
        assert not COMMIT_REGEX.match(msg)

    def test_boundary_summary_too_long(self) -> None:
        summary = "x" * 101
        msg = f"P1: {summary} (INFRA)"
        assert not COMMIT_REGEX.match(msg)


class TestGateIdsFromYaml:
    """Gate IDs are loaded from gates.yaml as the single source of truth."""

    def test_gate_ids_not_empty(self) -> None:
        assert len(GATE_IDS) > 0, "Gate IDs must be loaded from gates.yaml"

    def test_gate_ids_contain_common_gates(self) -> None:
        for i in range(1, 10):
            assert f"C{i}" in GATE_IDS, f"Common gate C{i} must be in GATE_IDS"

    def test_gate_ids_contain_p1_gates(self) -> None:
        assert "G1.1" in GATE_IDS

    def test_gate_ids_contain_p25_gates(self) -> None:
        for i in range(1, 9):
            assert f"G25.{i}" in GATE_IDS

    def test_capability_ids_not_empty(self) -> None:
        assert len(CAPABILITY_IDS) > 0

    def test_capability_ids_contain_r01(self) -> None:
        assert "R01" in CAPABILITY_IDS

    def test_all_valid_refs_contains_infra_doc(self) -> None:
        assert "INFRA" in ALL_VALID_REFS
        assert "DOC" in ALL_VALID_REFS


class TestPhaseGates:
    """PHASE_GATES is derived from gates.yaml."""

    def test_phase_gates_has_p1(self) -> None:
        assert "P1" in PHASE_GATES

    def test_phase_gates_has_p25(self) -> None:
        assert "P25" in PHASE_GATES

    def test_phase_gates_p25_has_8_gates(self) -> None:
        assert len(PHASE_GATES["P25"]) == 8

    def test_phase_gates_values_are_subset_of_gate_ids(self) -> None:
        for _phase, gates in PHASE_GATES.items():
            for g in gates:
                assert g in GATE_IDS, (
                    f"PHASE_GATES[{_phase}] contains {g} not in GATE_IDS"
                )


class TestExtractRefs:
    """extract_refs parses REFs from commit messages."""

    def test_single_ref(self) -> None:
        refs = _cc.extract_refs("P1: test (INFRA)")
        assert refs == ["INFRA"]

    def test_multiple_refs(self) -> None:
        refs = _cc.extract_refs("P1: test (G1.1, G1.2, INFRA)")
        assert refs == ["G1.1", "G1.2", "INFRA"]

    def test_section_ref(self) -> None:
        refs = _cc.extract_refs("P1: test (§3.5, INFRA)")
        assert refs == ["§3.5", "INFRA"]

    def test_no_refs(self) -> None:
        refs = _cc.extract_refs("P1: test no parens")
        assert refs == []
