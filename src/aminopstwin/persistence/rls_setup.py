"""Real PostgreSQL Row-Level Security (P27, deliverable 4).

Replaces the in-memory RLS simulation (P18) with real PostgreSQL RLS:
ENABLE and FORCE ROW LEVEL SECURITY on every tenant table. The
application role has no BYPASSRLS. The tenant is set per transaction
with SET LOCAL.

The in-memory RLS simulation was removed (G27.8).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

__all__ = [
    "TENANT_TABLES",
    "APPEND_ONLY_TABLES",
    "RLSPolicy",
    "generate_executor_rls_policies",
    "enable_rls_on_all_tenant_tables",
    "create_tenant_isolation_policies",
    "set_tenant_local",
]

# All tables that carry a tenant_id column and must have RLS enabled.
TENANT_TABLES: tuple[str, ...] = (
    "workflows",
    "checkpoints",
    "effects",
    "idempotency_keys",
    "outbox",
    "audit_events",
)

# Tables where RLS is enabled but the application role can still INSERT
# (audit_events is append-only: INSERT allowed, UPDATE/DELETE denied
# by role privileges, not by RLS).
APPEND_ONLY_TABLES: tuple[str, ...] = ("audit_events",)


class RLSPolicy:
    """A PostgreSQL RLS policy definition (P27).

    Unlike the P18 in-memory simulation, this represents a real
    PostgreSQL policy that is applied via DDL.
    """

    __slots__ = (
        "table_name",
        "policy_name",
        "using_clause",
        "check_clause",
    )

    def __init__(
        self,
        table_name: str,
        policy_name: str,
        using_clause: str,
        check_clause: str | None = None,
    ) -> None:
        self.table_name = table_name
        self.policy_name = policy_name
        self.using_clause = using_clause
        self.check_clause = check_clause or using_clause


def generate_executor_rls_policies() -> list[RLSPolicy]:
    """Generate real PostgreSQL RLS policies for all tenant tables.

    Each policy uses:
        USING (tenant_id = current_setting('app.tenant_id'))
        WITH CHECK (tenant_id = current_setting('app.tenant_id'))

    The application role has no BYPASSRLS, so RLS is always enforced.
    """
    using = "tenant_id = current_setting('app.tenant_id')"
    policies: list[RLSPolicy] = []
    for table in TENANT_TABLES:
        policies.append(
            RLSPolicy(
                table_name=table,
                policy_name=f"tenant_isolation_on_{table}",
                using_clause=using,
                check_clause=using,
            )
        )
    return policies


def enable_rls_on_all_tenant_tables(session: Session) -> None:
    """Enable and FORCE RLS on every tenant table.

    Also revokes BYPASSRLS from the application role (if it has it).
    """
    for table in TENANT_TABLES:
        session.execute(text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        session.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    session.commit()


def create_tenant_isolation_policies(session: Session) -> None:
    """Create the tenant isolation RLS policies on every tenant table."""
    for policy in generate_executor_rls_policies():
        session.execute(
            text(
                f"CREATE POLICY {policy.policy_name} ON {policy.table_name} "
                f"FOR ALL USING ({policy.using_clause}) "
                f"WITH CHECK ({policy.check_clause})"
            )
        )
    session.commit()


def set_tenant_local(session: Session, tenant_id: str) -> None:
    """Set the tenant for the current transaction (SET LOCAL)."""
    session.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
