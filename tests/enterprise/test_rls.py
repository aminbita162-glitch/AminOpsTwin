"""Tests for PostgreSQL RLS policy generation (P27, G27.8).

The in-memory RLS simulation (P18) has been removed. RLS is now real
PostgreSQL, tested via testcontainers in test_rls_postgres.py.
"""

from __future__ import annotations

from aminopstwin.enterprise.rls import (
    EXECUTOR_RLS_TABLES,
    TENANT_TABLES,
    generate_executor_rls_policies,
)


class TestRLSPolicyGeneration:
    """G27.8 — policies are generated for all tenant tables."""

    def test_generate_returns_policies_for_all_tenant_tables(self) -> None:
        policies = generate_executor_rls_policies()
        table_names = [p.table_name for p in policies]
        assert set(table_names) == set(TENANT_TABLES)
        assert len(policies) == len(TENANT_TABLES)

    def test_each_policy_has_tenant_isolation_name(self) -> None:
        policies = generate_executor_rls_policies()
        for p in policies:
            assert p.policy_name == f"tenant_isolation_on_{p.table_name}"

    def test_using_clause_references_tenant_id_and_current_setting(self) -> None:
        policies = generate_executor_rls_policies()
        for p in policies:
            assert "tenant_id" in p.using_clause
            assert "current_setting" in p.using_clause

    def test_check_clause_present_for_write_isolation(self) -> None:
        policies = generate_executor_rls_policies()
        for p in policies:
            assert p.check_clause is not None
            assert "tenant_id" in p.check_clause

    def test_executor_rls_tables_alias_matches_tenant_tables(self) -> None:
        assert set(EXECUTOR_RLS_TABLES) == set(TENANT_TABLES)
