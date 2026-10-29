"""PostgreSQL Row-Level Security (P27, G27.8).

The in-memory RLS simulation (P18) has been removed. Row-level security
is now implemented as real PostgreSQL RLS: ENABLE and FORCE ROW LEVEL
SECURITY on every tenant table, with the application role having no
BYPASSRLS. The tenant is set per transaction with SET LOCAL.

The :func:`generate_executor_rls_policies` function generates the DDL
for the tenant isolation policies. The actual enforcement is done by
PostgreSQL, not by in-memory filtering.

See :mod:`aminopstwin.persistence.rls_setup` for the setup functions
that create and enable the policies.
"""

from __future__ import annotations

from aminopstwin.persistence.rls_setup import (
    TENANT_TABLES,
    RLSPolicy,
    generate_executor_rls_policies,
)

__all__ = [
    "RLSPolicy",
    "TENANT_TABLES",
    "EXECUTOR_RLS_TABLES",
    "generate_executor_rls_policies",
]

# Kept for backward compatibility with P18 tests and the gate commands.
EXECUTOR_RLS_TABLES = TENANT_TABLES
