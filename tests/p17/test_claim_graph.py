"""G17.1 — Claim Graph: depends_on, stale-claim detection (P17).

Tests that the ClaimGraph correctly detects stale claims (evidence hash
mismatch) and that a deliberate stale claim causes failure while a
clean tree passes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from aminopstwin.evidence.claim_graph import (
    ClaimGraph,
    ClaimRecord,
    StaleClaimError,
    compute_file_hash,
    load_claims_yaml,
    load_default_graph,
)

REPO_ROOT = Path(__file__).parent.parent.parent


def _make_record(
    claim_id: str,
    evidence_path: str,
    hash_val: str,
    depends_on: list[str] | None = None,
) -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        text="test claim",
        evidence_path=evidence_path,
        hash=hash_val,
        category="test",
        depends_on=depends_on or [],
    )


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestClaimGraph:
    """G17.1: claim graph with depends_on and stale-claim detection."""

    def test_clean_graph_passes(self, tmp_path: Path) -> None:
        """A clean tree (all hashes match) passes verify_graph."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")

        claims = [
            _make_record("C1", str(f1), _hash_file(f1)),
            _make_record("C2", str(f2), _hash_file(f2), depends_on=["C1"]),
        ]
        graph = ClaimGraph(claims, tmp_path)
        assert graph.verify_graph() is True

    def test_stale_claim_detected(self, tmp_path: Path) -> None:
        """A deliberate stale claim (wrong hash) is detected."""
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")

        claims = [
            _make_record("C1", str(f1), "0" * 64),  # wrong hash
        ]
        graph = ClaimGraph(claims, tmp_path)
        stale = graph.detect_stale_claims()
        assert len(stale) == 1
        assert stale[0][0] == "C1"
        assert graph.verify_graph() is False

    def test_missing_file_is_stale(self, tmp_path: Path) -> None:
        """A missing evidence file is detected as stale."""
        claims = [
            _make_record("C1", str(tmp_path / "nonexistent.txt"), "a" * 64),
        ]
        graph = ClaimGraph(claims, tmp_path)
        stale = graph.detect_stale_claims()
        assert len(stale) == 1
        assert stale[0][3] == "FILE_NOT_FOUND"

    def test_placeholder_hash_is_stale(self, tmp_path: Path) -> None:
        """A PLACEHOLDER hash is detected as stale."""
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        claims = [
            _make_record("C1", str(f1), "PLACEHOLDER"),
        ]
        graph = ClaimGraph(claims, tmp_path)
        stale = graph.detect_stale_claims()
        assert len(stale) == 1
        assert stale[0][3] == "PLACEHOLDER_NOT_COMPUTED"

    def test_missing_dependency_fails(self, tmp_path: Path) -> None:
        """A depends_on pointing to a missing claim fails verify_graph."""
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        claims = [
            _make_record("C1", str(f1), _hash_file(f1), depends_on=["C_MISSING"]),
        ]
        graph = ClaimGraph(claims, tmp_path)
        # No stale claims, but missing dep.
        assert graph.detect_stale_claims() == []
        assert graph.verify_graph() is False
        missing = graph.missing_dependencies()
        assert ("C1", "C_MISSING") in missing

    def test_topological_sort(self, tmp_path: Path) -> None:
        """Topological sort puts dependencies before dependents."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f3 = tmp_path / "c.txt"
        f1.write_text("1")
        f2.write_text("2")
        f3.write_text("3")

        claims = [
            _make_record("C3", str(f3), _hash_file(f3), depends_on=["C2"]),
            _make_record("C2", str(f2), _hash_file(f2), depends_on=["C1"]),
            _make_record("C1", str(f1), _hash_file(f1)),
        ]
        graph = ClaimGraph(claims, tmp_path)
        order = graph.topological_sort()
        # C1 must come before C2, which must come before C3.
        assert order.index("C1") < order.index("C2")
        assert order.index("C2") < order.index("C3")

    def test_cycle_detection(self, tmp_path: Path) -> None:
        """A cycle in depends_on raises ValueError."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("1")
        f2.write_text("2")

        claims = [
            _make_record("C1", str(f1), _hash_file(f1), depends_on=["C2"]),
            _make_record("C2", str(f2), _hash_file(f2), depends_on=["C1"]),
        ]
        graph = ClaimGraph(claims, tmp_path)
        with pytest.raises(ValueError, match="cycle"):
            graph.topological_sort()

    def test_dependents_of(self, tmp_path: Path) -> None:
        """dependents_of returns claims that depend on the given ID."""
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("1")
        f2.write_text("2")

        claims = [
            _make_record("C1", str(f1), _hash_file(f1)),
            _make_record("C2", str(f2), _hash_file(f2), depends_on=["C1"]),
        ]
        graph = ClaimGraph(claims, tmp_path)
        assert graph.dependents_of("C1") == ["C2"]
        assert graph.dependents_of("C2") == []

    def test_dependencies_of(self, tmp_path: Path) -> None:
        """dependencies_of returns the depends_on list."""
        f1 = tmp_path / "a.txt"
        f1.write_text("1")
        claims = [
            _make_record("C1", str(f1), _hash_file(f1), depends_on=["C0", "C00"]),
        ]
        graph = ClaimGraph(claims, tmp_path)
        assert graph.dependencies_of("C1") == ["C0", "C00"]
        assert graph.dependencies_of("NONEXIST") == []

    def test_stale_claim_error_message(self, tmp_path: Path) -> None:
        """StaleClaimError carries the stale claim details."""
        f1 = tmp_path / "a.txt"
        f1.write_text("hello")
        claims = [
            _make_record("C1", str(f1), "0" * 64),
        ]
        graph = ClaimGraph(claims, tmp_path)
        stale = graph.detect_stale_claims()
        error = StaleClaimError(stale)
        assert "C1" in str(error)

    def test_compute_file_hash_file(self, tmp_path: Path) -> None:
        """compute_file_hash works on a single file."""
        f = tmp_path / "test.txt"
        f.write_text("hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert compute_file_hash(f) == expected

    def test_compute_file_hash_directory(self, tmp_path: Path) -> None:
        """compute_file_hash works on a directory."""
        d = tmp_path / "subdir"
        d.mkdir()
        f1 = d / "a.txt"
        f2 = d / "b.txt"
        f1.write_text("1")
        f2.write_text("2")
        # Should not raise.
        h = compute_file_hash(d)
        assert len(h) == 64

    def test_load_claims_yaml(self) -> None:
        """load_claims_yaml parses the real claims.yaml."""
        claims = load_claims_yaml(REPO_ROOT / "docs" / "claims.yaml")
        assert len(claims) > 0
        assert all(c.claim_id.startswith("CLAIM-") for c in claims)

    def test_load_default_graph_clean(self) -> None:
        """The real repo's claims.yaml has no stale claims."""
        graph = load_default_graph(REPO_ROOT)
        stale = graph.detect_stale_claims()
        assert stale == [], f"stale claims in real repo: {stale}"

    def test_get_claim(self, tmp_path: Path) -> None:
        """get returns the ClaimRecord or None."""
        f = tmp_path / "a.txt"
        f.write_text("1")
        claims = [_make_record("C1", str(f), _hash_file(f))]
        graph = ClaimGraph(claims, tmp_path)
        assert graph.get("C1") is not None
        assert graph.get("NONEXIST") is None

    def test_deliberate_stale_causes_failure(self, tmp_path: Path) -> None:
        """G17.1 acceptance: a deliberate stale claim causes verification failure."""
        f = tmp_path / "evidence.txt"
        f.write_text("original content")
        correct_hash = _hash_file(f)

        # Now tamper the file.
        f.write_text("tampered content")
        tampered_hash = _hash_file(f)
        assert correct_hash != tampered_hash

        # Record with the correct (now-stale) hash.
        claims = [_make_record("C1", str(f), correct_hash)]
        graph = ClaimGraph(claims, tmp_path)
        assert graph.verify_graph() is False
        stale = graph.detect_stale_claims()
        assert len(stale) == 1
