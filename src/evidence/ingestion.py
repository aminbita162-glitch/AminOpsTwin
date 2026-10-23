"""Source ingestion with injection-security guards (P4, §30.4, G4.3).

A1 requests a registered source operation; S1 authorizes; S2 executes the
bounded adapter and records provenance. Extraction emits typed operational
candidates. A4 checks boundaries and evidence quality.

Security rules:
- Indirect-injection: source content is DATA, never instruction. A source
  instruction that attempts to override policy, credentials, or runtime
  permissions is quarantined (GW-INJ-002).
- Redirects to local/private-network targets are denied unless explicitly
  approved.
- Oversized inputs, unsupported fields, and non-English content are rejected
  or quarantined.
- No source instruction acquires runtime authority.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.evidence.source_rights import SourceRegistry, SourceStatus

__all__ = [
    "IngestionOutcome",
    "IngestionResult",
    "SourceIngestor",
    "IngestionError",
]

#: Maximum content size for a single source excerpt (bytes).
_MAX_CONTENT_SIZE: int = 1024 * 1024  # 1 MiB

#: Allowed content languages (§0.2, §30.2).
_ALLOWED_LANGUAGES: frozenset[str] = frozenset({"en", "en-US", "en-GB"})

#: Allowed retrieval endpoint schemes.
_ALLOWED_SCHEMES: frozenset[str] = frozenset(
    {"https", "http", "file", "internal"}
)

#: Forbidden endpoint hosts (local/private-network unless explicitly approved).
_FORBIDDEN_HOSTS: frozenset[str] = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "10.0.0.1",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
    }
)

#: Regex to detect instruction-override patterns in source content.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?",
        re.IGNORECASE,
    ),
    re.compile(
        r"disregard\s+(?:the\s+)?(?:policy|rules?|system\s+prompt)",
        re.IGNORECASE,
    ),
    re.compile(
        r"you\s+are\s+now\s+(?:a|an)\s+(?:different|new)\s+(?:system|agent|mode)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:pretend|act)\s+as\s+if\s+(?:policy|rules?|boundaries?)\s+(?:do\s+not|don'?t)\s+apply",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:override|bypass|disable|deactivate)\s+(?:the\s+)?(?:policy|gateway|security|filter)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:set|change|update)\s+(?:the\s+)?(?:credentials?|api[_\s-]?key|token|secret)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:grant|give)\s+(?:me|us)\s+(?:full|admin|root|super)\s+(?:access|permissions?|privileges?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:execute|run|eval)\s+(?:the\s+)?(?:following|this)\s+(?:command|code|script|payload)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:ignore|skip|disable)\s+(?:the\s+)?(?:boundary|safety|medical|clinical)\s+(?:check|review|filter)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:system|developer|admin)\s*(?:prompt|instruction|override)",
        re.IGNORECASE,
    ),
)

#: Allowed field names for extracted operational candidates.
_ALLOWED_FIELDS: frozenset[str] = frozenset(
    {
        "source_id",
        "title",
        "publisher",
        "license",
        "claim_span",
        "operational_metric",
        "assumption",
        "method_reference",
        "aggregate_count",
        "site",
        "slot",
        "capacity",
        "queue",
        "resource",
        "schedule",
        "milestone",
        "throughput",
        "wait_time",
        "utilization",
        "staffing_role",
        "protocol_milestone",
        "scenario",
    }
)

#: Forbidden field names that model individual patient state (N-1, §2.2).
_FORBIDDEN_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "patient_id",
        "patient_name",
        "diagnosis",
        "prognosis",
        "treatment",
        "dose",
        "eligibility",
        "triage",
        "physiology",
        "individual_risk",
        "health_status",
        "patient_state",
    }
)


class IngestionOutcome(StrEnum):
    """Outcome of a source ingestion attempt."""

    ADMITTED = "ADMITTED"
    REJECTED_OVERSIZED = "REJECTED_OVERSIZED"
    REJECTED_UNSUPPORTED_FIELD = "REJECTED_UNSUPPORTED_FIELD"
    REJECTED_FORBIDDEN_FIELD = "REJECTED_FORBIDDEN_FIELD"
    REJECTED_NON_ENGLISH = "REJECTED_NON_ENGLISH"
    REJECTED_UNAPPROVED_SOURCE = "REJECTED_UNAPPROVED_SOURCE"
    REJECTED_UNREGISTERED_SOURCE = "REJECTED_UNREGISTERED_SOURCE"
    QUARANTINED_INJECTION = "QUARANTINED_INJECTION"
    REJECTED_FORBIDDEN_REDIRECT = "REJECTED_FORBIDDEN_REDIRECT"


class IngestionError(Exception):
    """Raised when ingestion encounters a configuration error (not a rejection)."""


class IngestionResult(BaseModel):
    """Result of a single source ingestion (§30.4, G4.3).

    model_config: frozen, strict, extra="forbid".
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str
    outcome: IngestionOutcome
    reason_code: str
    content_hash: str | None = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    quarantined: bool = False
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class SourceIngestor:
    """Bounded source adapter with injection-security guards (§30.4, G4.3).

    Ingestion flow:
    1. Check source is registered and approved/active (GW-EVID-002).
    2. Validate content size (oversized -> reject).
    3. Validate content language (non-English -> reject).
    4. Validate retrieval endpoint (forbidden redirect -> reject).
    5. Scan content for instruction-injection patterns (quarantine).
    6. Validate extracted fields (unsupported/forbidden -> reject).
    7. Emit typed operational candidates.
    """

    def __init__(self, registry: SourceRegistry) -> None:
        self._registry = registry

    def ingest(
        self,
        source_id: str,
        content: str,
        endpoint: str = "",
        language: str = "en",
        extracted_fields: dict[str, Any] | None = None,
    ) -> IngestionResult:
        """Ingest a single source excerpt with security guards."""
        fields = extracted_fields or {}

        # 1. Source must be registered and approved/active.
        record = self._registry.get(source_id)
        if record is None:
            return IngestionResult(
                source_id=source_id,
                outcome=IngestionOutcome.REJECTED_UNREGISTERED_SOURCE,
                reason_code="GW-EVID-002",
            )
        if not self._registry.is_approved(source_id):
            return IngestionResult(
                source_id=source_id,
                outcome=IngestionOutcome.REJECTED_UNAPPROVED_SOURCE,
                reason_code="GW-EVID-002",
            )

        # 2. Content size check.
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > _MAX_CONTENT_SIZE:
            return IngestionResult(
                source_id=source_id,
                outcome=IngestionOutcome.REJECTED_OVERSIZED,
                reason_code="GW-INJ-002",
            )

        # 3. Language check.
        if language not in _ALLOWED_LANGUAGES:
            return IngestionResult(
                source_id=source_id,
                outcome=IngestionOutcome.REJECTED_NON_ENGLISH,
                reason_code="GW-INJ-002",
            )

        # 4. Endpoint / redirect check.
        if endpoint:
            scheme = self._parse_scheme(endpoint)
            if scheme not in _ALLOWED_SCHEMES:
                return IngestionResult(
                    source_id=source_id,
                    outcome=IngestionOutcome.REJECTED_FORBIDDEN_REDIRECT,
                    reason_code="GW-INJ-002",
                )
            host = self._parse_host(endpoint)
            if host and host in _FORBIDDEN_HOSTS:
                return IngestionResult(
                    source_id=source_id,
                    outcome=IngestionOutcome.REJECTED_FORBIDDEN_REDIRECT,
                    reason_code="GW-INJ-002",
                )

        # 5. Injection scan — source content is DATA, never instruction.
        injection_hit = self._detect_injection(content)
        if injection_hit is not None:
            # Quarantine the source: it cannot enter the cache.
            self._registry.transition(
                source_id, SourceStatus.QUARANTINED, reason=injection_hit
            )
            return IngestionResult(
                source_id=source_id,
                outcome=IngestionOutcome.QUARANTINED_INJECTION,
                reason_code="GW-INJ-002",
                quarantined=True,
            )

        # 6. Field validation.
        for fname in fields:
            if fname in _FORBIDDEN_FIELD_NAMES:
                return IngestionResult(
                    source_id=source_id,
                    outcome=IngestionOutcome.REJECTED_FORBIDDEN_FIELD,
                    reason_code="GW-CLIN-002",
                )
            if fname not in _ALLOWED_FIELDS:
                return IngestionResult(
                    source_id=source_id,
                    outcome=IngestionOutcome.REJECTED_UNSUPPORTED_FIELD,
                    reason_code="GW-DEFAULT-001",
                )

        # 7. Compute content hash for provenance.
        import hashlib

        content_hash = hashlib.sha256(content_bytes).hexdigest()

        return IngestionResult(
            source_id=source_id,
            outcome=IngestionOutcome.ADMITTED,
            reason_code="",
            content_hash=content_hash,
            extracted_fields=dict(fields),
            quarantined=False,
        )

    @staticmethod
    def _detect_injection(content: str) -> str | None:
        """Return the first matched injection pattern name, or None."""
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(content):
                return f"injection_pattern: {pattern.pattern}"
        return None

    @staticmethod
    def _parse_scheme(url: str) -> str:
        """Extract the scheme from a URL-like string."""
        if "://" in url:
            return url.split("://")[0].lower()
        return ""

    @staticmethod
    def _parse_host(url: str) -> str:
        """Extract the host from a URL-like string."""
        rest = url.split("://", 1)[1] if "://" in url else url
        # Strip path and port
        host = rest.split("/")[0].split(":")[0].lower()
        return host
