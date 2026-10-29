"""Test that the in-memory RLS simulation is removed (P27, G27.8).

The P18 in-memory RLS simulation has been replaced by real PostgreSQL
RLS.  This test verifies that no in-memory simulation remains in the
source code: no RLS filtering logic that runs in Python, only DDL
generation for PostgreSQL.

G27.8: grep for the in-memory RLS simulation -> removed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent.parent / "src" / "aminopstwin"


class TestRLSSimulationRemoved:
    """G27.8 — the in-memory RLS simulation has been removed."""

    def test_no_in_memory_filter_in_rls_py(self) -> None:
        """enterprise/rls.py must not contain in-memory filtering logic."""
        rls_file = SRC / "enterprise" / "rls.py"
        content = rls_file.read_text(encoding="utf-8")
        # The file must re-export from persistence.rls_setup, not
        # implement in-memory filtering.
        assert "persistence.rls_setup" in content
        # Must not contain an in-memory filter function that filters
        # rows by tenant_id in Python.
        assert "def filter_" not in content
        assert "def in_memory" not in content

    def test_rls_setup_is_ddl_only(self) -> None:
        """persistence/rls_setup.py must generate DDL, not filter in memory."""
        rls_setup = SRC / "persistence" / "rls_setup.py"
        content = rls_setup.read_text(encoding="utf-8")
        # Must contain DDL generation (ALTER TABLE, CREATE POLICY).
        assert "ALTER TABLE" in content
        assert "CREATE POLICY" in content
        assert "ENABLE ROW LEVEL SECURITY" in content
        assert "FORCE ROW LEVEL SECURITY" in content
        # Must not contain in-memory row filtering.
        assert "def filter_rows" not in content
        assert "def simulate_rls" not in content

    def test_no_in_memory_rls_simulation_classes(self) -> None:
        """No InMemoryRLS or RLSFilter class should exist in the source."""
        for py_file in SRC.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            # These class names indicate in-memory simulation.
            assert "class InMemoryRLS" not in content, (
                f"InMemoryRLS found in {py_file}"
            )
            assert "class RLSFilter" not in content, (
                f"RLSFilter found in {py_file}"
            )
            assert "class RLSimulation" not in content, (
                f"RLSimulation found in {py_file}"
            )

    def test_rls_re_exports_tenant_tables_from_persistence(self) -> None:
        """enterprise/rls.py re-exports from persistence.rls_setup."""
        rls_file = SRC / "enterprise" / "rls.py"
        content = rls_file.read_text(encoding="utf-8")
        assert "TENANT_TABLES" in content
        assert "generate_executor_rls_policies" in content

    @pytest.mark.parametrize(
        "table",
        [
            "workflows",
            "checkpoints",
            "effects",
            "idempotency_keys",
            "outbox",
            "audit_events",
        ],
    )
    def test_tenant_tables_include_all_p27_tables(self, table: str) -> None:
        """All P27 tenant tables must be in TENANT_TABLES."""
        from aminopstwin.persistence.rls_setup import TENANT_TABLES

        assert table in TENANT_TABLES, (
            f"{table} missing from TENANT_TABLES"
        )

    def test_no_simulated_until_p27_claims(self) -> None:
        """No 'simulated until P27' or similar stale claims remain."""
        # P27 replaced the simulation; any remaining claim that RLS is
        # simulated is a defect.
        for py_file in SRC.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            # Allow the docstring that says the simulation WAS removed.
            if "simulation" in content.lower():
                # Must say "removed" or "replaced", not "simulated until".
                assert not re.search(
                    r"simulated.*until\s*P\s*2\s*7",
                    content,
                    re.IGNORECASE,
                ), f"Stale 'simulated until P27' claim in {py_file}"
