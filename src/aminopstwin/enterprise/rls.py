"""PostgreSQL Row-Level Security simulation (P18, G18.3).

Row-level security is an in-memory simulation until P27.  The
simulation models the behaviour of
``CREATE POLICY ... USING (tenant_id = current_setting('app.tenant_id'))``
on executor tables (``workflow_records``, ``checkpoints``) keyed on
``tenant_id``.

A real PostgreSQL deployment would emit ``rls.py``-generated policies as
``ALTER TABLE ... ENABLE ROW LEVEL SECURITY`` DDL with the corresponding
``CREATE POLICY`` statements.  The simulation mirrors that behaviour:
``select`` returns only the requesting tenant's rows, ``select_all`` is
the ``BYPASSRLS`` admin path, and ``attempt_cross_tenant_select`` is the
raw-SQL adversarial probe used to verify zero leakage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "RLSPolicy",
    "RLSEngine",
    "generate_executor_rls_policies",
]


# Executor tables that must carry a tenant isolation RLS policy.
EXECUTOR_RLS_TABLES: tuple[str, ...] = ("workflow_records", "checkpoints")


@dataclass(frozen=True)
class RLSPolicy:
    """A single PostgreSQL RLS policy definition (G18.3).

    Attributes
    ----------
    tenant_id:
        Placeholder tenant-id column reference used by the policy
        (``tenant_id``).  Kept as a field so policies can be keyed and
        inspected uniformly.
    table_name:
        Table on which the policy is declared.
    policy_name:
        PostgreSQL policy name (``tenant_isolation_on_<table>``).
    using_clause:
        ``USING`` expression — rows visible only when this evaluates
        true under the requesting session's ``app.tenant_id`` setting.
    check_clause:
        Optional ``WITH CHECK`` expression for writes.
    """

    tenant_id: str
    table_name: str
    policy_name: str
    using_clause: str
    check_clause: str | None = None


def generate_executor_rls_policies() -> list[RLSPolicy]:
    """Generate RLS policies for executor tables (G18.3).

    Returns one :class:`RLSPolicy` per executor table in
    :data:`EXECUTOR_RLS_TABLES`, each keyed on ``tenant_id`` with a
    ``USING`` clause of the form
    ``tenant_id = current_setting('app.tenant_id')`` and a matching
    ``WITH CHECK`` clause so writes are also tenant-scoped.
    """
    using = 'tenant_id = current_setting(\'app.tenant_id\')'
    policies: list[RLSPolicy] = []
    for table in EXECUTOR_RLS_TABLES:
        policies.append(
            RLSPolicy(
                tenant_id="tenant_id",
                table_name=table,
                policy_name=f"tenant_isolation_on_{table}",
                using_clause=using,
                check_clause=using,
            )
        )
    return policies


class RLSEngine:
    """In-memory Row-Level Security simulation (G18.3).

    Models the runtime behaviour of PostgreSQL RLS: each table is a
    ``dict[record_id, record]`` and every record carries a ``tenant_id``
    field.  ``select`` filters by the requesting tenant just as a
    ``USING (tenant_id = current_setting('app.tenant_id'))`` policy would.
    """

    def __init__(self) -> None:
        self._tables: dict[str, dict[str, dict[str, Any]]] = {}
        self._policies: dict[str, list[RLSPolicy]] = {}

    # ------------------------------------------------------------------
    # Policy management
    # ------------------------------------------------------------------

    def apply_policy(self, policy: RLSPolicy) -> None:
        """Register an RLS *policy* on its table."""
        self._policies.setdefault(policy.table_name, []).append(policy)
        # Ensure the table exists for the policy's table.
        self._tables.setdefault(policy.table_name, {})

    def get_policies(self, table_name: str) -> list[RLSPolicy]:
        """Return the policies registered on *table_name* (empty if none)."""
        return list(self._policies.get(table_name, []))

    def verify_rls(self, table_name: str) -> bool:
        """Return True iff *table_name* has a tenant-isolation RLS policy.

        A policy qualifies when its ``using_clause`` references
        ``tenant_id`` and ``current_setting`` — i.e. it actually
        enforces tenant isolation rather than being a no-op policy.
        """
        policies = self._policies.get(table_name, [])
        if not policies:
            return False
        for p in policies:
            if "tenant_id" not in p.using_clause:
                return False
            if "current_setting" not in p.using_clause:
                return False
        return True

    # ------------------------------------------------------------------
    # Data access
    # ------------------------------------------------------------------

    def _table(self, table_name: str) -> dict[str, dict[str, Any]]:
        return self._tables.setdefault(table_name, {})

    def insert(
        self,
        table_name: str,
        record_id: str,
        tenant_id: str,
        data: dict[str, Any],
    ) -> None:
        """Insert a record tagged with *tenant_id* into *table_name*.

        The stored record is a copy of *data* augmented with the
        ``tenant_id`` field and the ``record_id`` for traceability.
        """
        if not tenant_id:
            raise ValueError("tenant_id must be non-empty")
        record: dict[str, Any] = {
            "record_id": record_id,
            "tenant_id": tenant_id,
            **dict(data),
        }
        self._table(table_name)[record_id] = record

    def select(
        self,
        table_name: str,
        requesting_tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Return only the requesting tenant's records (RLS filter, G18.3).

        Mirrors ``SELECT ... FROM <table> WHERE tenant_id =
        current_setting('app.tenant_id')``: only rows whose
        ``tenant_id`` equals *requesting_tenant_id* are returned.
        """
        table = self._table(table_name)
        return [
            dict(record)
            for record in table.values()
            if record.get("tenant_id") == requesting_tenant_id
        ]

    def select_all(self, table_name: str) -> list[dict[str, Any]]:
        """Admin bypass — return all rows regardless of tenant (testing only)."""
        table = self._table(table_name)
        return [dict(record) for record in table.values()]

    def attempt_cross_tenant_select(
        self,
        table_name: str,
        requesting_tenant_id: str,
    ) -> list[dict[str, Any]]:
        """Adversarial raw-SQL probe (G18.3).

        Identical to :meth:`select` — used to assert that a session
        scoped to *requesting_tenant_id* cannot read any other tenant's
        rows.  Under real RLS this returns zero rows from other tenants;
        the simulation returns the requesting tenant's rows (which is
        the same empty set when probing for *other* tenants' data).
        """
        return self.select(table_name, requesting_tenant_id)
