"""Tests for PostgreSQL RLS simulation (P18, G18.3)."""

from __future__ import annotations

import pytest
from aminopstwin.enterprise.rls import (
    EXECUTOR_RLS_TABLES,
    RLSEngine,
    RLSPolicy,
    generate_executor_rls_policies,
)


class TestRLSPolicyGeneration:
    """G18.3 — policies are generated for executor tables."""

    def test_generate_returns_policies_for_executor_tables(self) -> None:
        policies = generate_executor_rls_policies()
        table_names = [p.table_name for p in policies]
        assert set(table_names) == set(EXECUTOR_RLS_TABLES)
        assert len(policies) == len(EXECUTOR_RLS_TABLES)

    def test_each_policy_has_tenant_isolation_name(self) -> None:
        policies = generate_executor_rls_policies()
        for p in policies:
            assert p.policy_name == f"tenant_isolation_on_{p.table_name}"

    def test_using_clause_references_tenant_id_and_current_setting(self) -> None:
        policies = generate_executor_rls_policies()
        for p in policies:
            assert "tenant_id" in p.using_clause
            assert "current_setting" in p.using_clause
            assert p.tenant_id == "tenant_id"

    def test_check_clause_present_for_write_isolation(self) -> None:
        policies = generate_executor_rls_policies()
        for p in policies:
            assert p.check_clause is not None
            assert "tenant_id" in p.check_clause


class TestRLSSelect:
    """G18.3 — select returns only the requesting tenant's records."""

    def test_select_returns_only_requesting_tenant_records(self) -> None:
        engine = RLSEngine()
        for p in generate_executor_rls_policies():
            engine.apply_policy(p)
        engine.insert("workflow_records", "r1", "tenant-a", {"status": "ok"})
        engine.insert("workflow_records", "r2", "tenant-b", {"status": "ok"})
        engine.insert("workflow_records", "r3", "tenant-a", {"status": "fail"})

        rows = engine.select("workflow_records", "tenant-a")
        assert len(rows) == 2
        assert {r["record_id"] for r in rows} == {"r1", "r3"}
        assert all(r["tenant_id"] == "tenant-a" for r in rows)

    def test_select_empty_for_tenant_with_no_records(self) -> None:
        engine = RLSEngine()
        for p in generate_executor_rls_policies():
            engine.apply_policy(p)
        engine.insert("workflow_records", "r1", "tenant-a", {"status": "ok"})
        rows = engine.select("workflow_records", "tenant-z")
        assert rows == []


class TestCrossTenantSelect:
    """G18.3 — cross-tenant select returns zero leakage."""

    def test_cross_tenant_select_returns_empty_for_other_tenant(self) -> None:
        engine = RLSEngine()
        for p in generate_executor_rls_policies():
            engine.apply_policy(p)
        engine.insert("workflow_records", "r1", "tenant-a", {"v": 1})
        engine.insert("workflow_records", "r2", "tenant-b", {"v": 2})
        # A session for tenant-b cannot read tenant-a's rows.
        leaked = engine.attempt_cross_tenant_select(
            "workflow_records", "tenant-b"
        )
        assert all(r["tenant_id"] == "tenant-b" for r in leaked)
        assert not any(r["tenant_id"] == "tenant-a" for r in leaked)


class TestInsert:
    """G18.3 — insert tags records with tenant_id."""

    def test_insert_tags_record_with_tenant_id(self) -> None:
        engine = RLSEngine()
        engine.insert("workflow_records", "r1", "tenant-a", {"status": "ok"})
        all_rows = engine.select_all("workflow_records")
        assert len(all_rows) == 1
        assert all_rows[0]["tenant_id"] == "tenant-a"
        assert all_rows[0]["status"] == "ok"
        assert all_rows[0]["record_id"] == "r1"

    def test_insert_empty_tenant_id_raises(self) -> None:
        engine = RLSEngine()
        with pytest.raises(ValueError, match="tenant_id must be non-empty"):
            engine.insert("workflow_records", "r1", "", {"v": 1})


class TestMultiTenantIsolation:
    """G18.3 — with 3+ tenants each only sees their own records."""

    def test_three_tenants_each_see_own_records_only(self) -> None:
        engine = RLSEngine()
        for p in generate_executor_rls_policies():
            engine.apply_policy(p)
        tenants = ["tenant-a", "tenant-b", "tenant-c"]
        for i, t in enumerate(tenants):
            engine.insert("workflow_records", f"r-{t}-1", t, {"seq": i * 2})
            engine.insert("workflow_records", f"r-{t}-2", t, {"seq": i * 2 + 1})

        for t in tenants:
            rows = engine.select("workflow_records", t)
            assert len(rows) == 2
            assert all(r["tenant_id"] == t for r in rows)

        # Admin sees all 6.
        assert len(engine.select_all("workflow_records")) == 6

    def test_checkpoints_table_also_isolated(self) -> None:
        engine = RLSEngine()
        for p in generate_executor_rls_policies():
            engine.apply_policy(p)
        engine.insert("checkpoints", "c1", "tenant-a", {"step": 1})
        engine.insert("checkpoints", "c2", "tenant-b", {"step": 2})
        a_rows = engine.select("checkpoints", "tenant-a")
        assert len(a_rows) == 1
        assert a_rows[0]["record_id"] == "c1"


class TestVerifyRLS:
    """G18.3 — verify_rls returns True for tables with RLS policies."""

    def test_verify_rls_true_after_applying_policies(self) -> None:
        engine = RLSEngine()
        for p in generate_executor_rls_policies():
            engine.apply_policy(p)
        assert engine.verify_rls("workflow_records") is True
        assert engine.verify_rls("checkpoints") is True

    def test_verify_rls_false_without_policy(self) -> None:
        engine = RLSEngine()
        assert engine.verify_rls("workflow_records") is False

    def test_verify_rls_false_for_non_tenant_policy(self) -> None:
        engine = RLSEngine()
        bogus = RLSPolicy(
            tenant_id="tenant_id",
            table_name="workflow_records",
            policy_name="noop",
            using_clause="true",
            check_clause=None,
        )
        engine.apply_policy(bogus)
        assert engine.verify_rls("workflow_records") is False


class TestGetPolicies:
    """G18.3 — get_policies returns registered policies."""

    def test_get_policies_returns_registered(self) -> None:
        engine = RLSEngine()
        for p in generate_executor_rls_policies():
            engine.apply_policy(p)
        wfp = engine.get_policies("workflow_records")
        assert len(wfp) == 1
        assert wfp[0].table_name == "workflow_records"

    def test_get_policies_empty_for_unregistered_table(self) -> None:
        engine = RLSEngine()
        assert engine.get_policies("nope") == []
