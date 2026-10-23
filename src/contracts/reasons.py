"""Versioned reason-code registry for the Policy Gateway and schema validation stage.

Every denial returns exactly one primary reason code and optional secondary codes.
Codes are never reused or renumbered; retired codes stay in the registry marked RETIRED.

Reason code format: GW-<DOMAIN>-<NNN> where DOMAIN is one of:
    CLIN, INJ, SCHEMA, AUTH, IDEM, TENANT, BUDGET, EVID, EPOCH, DEFAULT.

Seed registry (OWNER-CONFIRM in §6.4):
    GW-DEFAULT-001 unknown/unlisted action, schema_id, or envelope_type (deny-by-default)
    GW-SCHEMA-001  payload or envelope fails schema validation (incl. forbidden "issuer" key)
    GW-SCHEMA-002  payload_hash does not match recomputed canonical hash
    GW-SCHEMA-003  unsupported envelope_version
    GW-SCHEMA-004  forbidden payload value type (float, NaN, Infinity, non-NFC string)
    GW-SCHEMA-005  event out of sequence beyond the allowed window
    GW-AUTH-001    (principal, envelope_type, capability) not in policy_matrix
    GW-IDEM-001    idempotency_key reused with a different payload_hash
    GW-CLIN-001    request or output touches a forbidden clinical category (§2.2)
    GW-CLIN-002    forbidden structure (field or value modeling individual patient state)
    GW-INJ-001     direct instruction-override attempt
    GW-INJ-002     instruction embedded in retrieved/source content (indirect injection)
    GW-EVID-001    cache entry binding mismatch (tampered or stale source/claim/window)
    GW-EVID-002    source not in the approved register
    GW-EPOCH-001   envelope bound to an outdated policy_epoch
    GW-EPOCH-002   envelope bound to a future policy_epoch
    GW-BUDGET-001  budget exhausted (deterministic fallback path)
    GW-TENANT-001  cross-tenant access attempt
"""

from __future__ import annotations

from enum import Enum
from typing import Final


class ReasonDomain(str, Enum):
    """Domains for reason codes (§6.4)."""

    CLIN = "CLIN"
    INJ = "INJ"
    SCHEMA = "SCHEMA"
    AUTH = "AUTH"
    IDEM = "IDEM"
    TENANT = "TENANT"
    BUDGET = "BUDGET"
    EVID = "EVID"
    EPOCH = "EPOCH"
    DEFAULT = "DEFAULT"


class CodeStatus(str, Enum):
    """Lifecycle status of a reason code."""

    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


# --- Seed registry: code -> (domain, description, status) ---
# Codes are never reused or renumbered; retired codes stay marked RETIRED.

_SEED_REGISTRY: Final[dict[str, tuple[str, str, CodeStatus]]] = {
    "GW-DEFAULT-001": ("DEFAULT", "unknown/unlisted action, schema_id, or envelope_type (deny-by-default)", CodeStatus.ACTIVE),
    "GW-SCHEMA-001": ("SCHEMA", "payload or envelope fails schema validation (incl. forbidden issuer key)", CodeStatus.ACTIVE),
    "GW-SCHEMA-002": ("SCHEMA", "payload_hash does not match recomputed canonical hash", CodeStatus.ACTIVE),
    "GW-SCHEMA-003": ("SCHEMA", "unsupported envelope_version", CodeStatus.ACTIVE),
    "GW-SCHEMA-004": ("SCHEMA", "forbidden payload value type (float, NaN, Infinity, non-NFC string)", CodeStatus.ACTIVE),
    "GW-SCHEMA-005": ("SCHEMA", "event out of sequence beyond the allowed window", CodeStatus.ACTIVE),
    "GW-AUTH-001": ("AUTH", "(principal, envelope_type, capability) not in policy_matrix", CodeStatus.ACTIVE),
    "GW-IDEM-001": ("IDEM", "idempotency_key reused with a different payload_hash", CodeStatus.ACTIVE),
    "GW-CLIN-001": ("CLIN", "request or output touches a forbidden clinical category (§2.2)", CodeStatus.ACTIVE),
    "GW-CLIN-002": ("CLIN", "forbidden structure (field or value modeling individual patient state)", CodeStatus.ACTIVE),
    "GW-INJ-001": ("INJ", "direct instruction-override attempt", CodeStatus.ACTIVE),
    "GW-INJ-002": ("INJ", "instruction embedded in retrieved/source content (indirect injection)", CodeStatus.ACTIVE),
    "GW-EVID-001": ("EVID", "cache entry binding mismatch (tampered or stale source/claim/window)", CodeStatus.ACTIVE),
    "GW-EVID-002": ("EVID", "source not in the approved register", CodeStatus.ACTIVE),
    "GW-EPOCH-001": ("EPOCH", "envelope bound to an outdated policy_epoch", CodeStatus.ACTIVE),
    "GW-EPOCH-002": ("EPOCH", "envelope bound to a future policy_epoch", CodeStatus.ACTIVE),
    "GW-BUDGET-001": ("BUDGET", "budget exhausted (deterministic fallback path)", CodeStatus.ACTIVE),
    "GW-TENANT-001": ("TENANT", "cross-tenant access attempt", CodeStatus.ACTIVE),
}


class ReasonCode:
    """A single reason-code entry in the registry."""

    __slots__ = ("code", "domain", "description", "status")

    def __init__(self, code: str, domain: str, description: str, status: CodeStatus) -> None:
        self.code = code
        self.domain = domain
        self.description = description
        self.status = status

    def __repr__(self) -> str:
        return f"ReasonCode({self.code!r}, {self.domain!r}, status={self.status.value})"


def _build_registry() -> dict[str, ReasonCode]:
    registry: dict[str, ReasonCode] = {}
    for code, (domain, desc, status) in _SEED_REGISTRY.items():
        registry[code] = ReasonCode(code, domain, desc, status)
    return registry


_REGISTRY: Final[dict[str, ReasonCode]] = _build_registry()


def get_reason_code(code: str) -> ReasonCode | None:
    """Return the ReasonCode for *code* if it exists in the registry, else None."""
    return _REGISTRY.get(code)


def is_known_code(code: str) -> bool:
    """Return True if *code* is a registered reason code (active or retired)."""
    return code in _REGISTRY


def all_codes() -> dict[str, ReasonCode]:
    """Return a copy of the full registry."""
    return dict(_REGISTRY)


def active_codes() -> dict[str, ReasonCode]:
    """Return only active (non-retired) reason codes."""
    return {k: v for k, v in _REGISTRY.items() if v.status == CodeStatus.ACTIVE}
