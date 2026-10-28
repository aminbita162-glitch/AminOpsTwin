"""Authority precedence levels (ADR-007).

The six-level hierarchy, highest level first:

1. LAW — law and the non-medical invariants, hard-coded and never
   overridable.
2. PLATFORM — platform security.
3. OWNER — owner governance, as a signed policy bundle.
4. TENANT — tenant administration, which may only narrow.
5. ROLE — role and user permissions.
6. AGENT — agent requests; LLM output carries zero authority.

A conflict at the same level resolves to DENY (deny-overrides).
"""

from __future__ import annotations

from enum import IntEnum

__all__ = ["AuthorityLevel", "DENY_OVERRIDES"]


class AuthorityLevel(IntEnum):
    """The six-level authority hierarchy (ADR-007).

    Lower integer = higher precedence. A lower-level ALLOW never flips a
    higher-level DENY.
    """

    LAW = 1
    PLATFORM = 2
    OWNER = 3
    TENANT = 4
    ROLE = 5
    AGENT = 6


#: Deny-overrides: at the same level, DENY wins over ALLOW.
DENY_OVERRIDES: bool = True
