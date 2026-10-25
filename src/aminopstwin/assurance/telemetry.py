"""Secure telemetry with explicit allow-list (P18, G18.5, Deliverable 5).

OpenTelemetry is not a dependency of this project, so this module provides a
structured-telemetry equivalent with an explicit field allow-list. Only fields
that appear on the allow-list are exported from spans; everything else is
dropped before export. This prevents accidental leakage of secrets, tokens,
passwords, api keys or raw payloads into exported telemetry.

A canary mechanism (:class:`TelemetryCanary`) supports the core security test:
inject a known secret into a span, export it through the allow-list, and verify
the canary never appears anywhere in the exported output.

Deterministic core: this module never calls ``datetime.now()``, ``uuid.uuid4``,
``random.*`` or ``secrets.*``. Timestamps are integer values supplied by the
caller, and the canary secret is a plain string literal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

__all__ = [
    "DEFAULT_TELEMETRY_ALLOWED_FIELDS",
    "SENSITIVE_FIELDS",
    "TelemetryField",
    "TelemetryAllowList",
    "TelemetryExporter",
    "TelemetryCanary",
    "default_telemetry_fields",
]


#: Default allow-list for exported spans — safe, non-sensitive fields only.
DEFAULT_TELEMETRY_ALLOWED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "trace_id",
        "span_id",
        "operation",
        "tenant_id",
        "duration_ms",
        "outcome",
        "timestamp",
    }
)

#: Field names that must NEVER appear in exported telemetry — they are
#: rejected by the default allow-list and are listed here for documentation
#: and test assertions. These are intentionally NOT part of the allow-list.
SENSITIVE_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "secret",
        "password",
        "token",
        "api_key",
        "payload",
    }
)


def default_telemetry_fields() -> set[str]:
    """Return a fresh copy of the default allowed-field set."""
    return set(DEFAULT_TELEMETRY_ALLOWED_FIELDS)


@dataclass(frozen=True)
class TelemetryField:
    """Definition of a single field that may appear in exported spans.

    Attributes
    ----------
    name:
        Field name as it appears in a span dict.
    value_type:
        Logical type name (e.g. ``"str"``, ``"int"``, ``"float"``).
    allowed_values:
        Optional closed set of permitted string values. When provided, a
        span field whose value is not in this set should be treated as
        schema-invalid by callers (this module does not enforce it on its
        own — it only describes the contract).
    """

    name: str
    value_type: str
    allowed_values: list[str] | None = None


class TelemetryAllowList:
    """Allow-list governing which span fields may be exported.

    Only fields whose names are in ``allowed_fields`` survive
    :meth:`filter_span`. All other fields — including any sensitive field —
    are dropped before export.
    """

    _allowed: set[str]

    def __init__(self, allowed_fields: set[str]) -> None:
        self._allowed = set(allowed_fields)

    @property
    def allowed_fields(self) -> set[str]:
        """Return a fresh copy of the allowed-field names."""
        return set(self._allowed)

    def is_allowed(self, field_name: str) -> bool:
        """Return True if *field_name* is on the allow-list."""
        return field_name in self._allowed

    def filter_span(self, span: dict[str, Any]) -> dict[str, Any]:
        """Return a dict containing ONLY allowed fields from *span*.

        Any field not on the allow-list is dropped. The returned dict is a
        new dict; the input span is not mutated.
        """
        return {
            key: value
            for key, value in span.items()
            if key in self._allowed
        }


class TelemetryExporter:
    """Export spans through a :class:`TelemetryAllowList`.

    Each exported span is the sanitized (filtered) form of the input span.
    Exported spans are retained in :attr:`spans` for inspection and
    canary scanning.
    """

    _allow_list: TelemetryAllowList
    _exported: list[dict[str, Any]]

    def __init__(self, allow_list: TelemetryAllowList) -> None:
        self._allow_list = allow_list
        self._exported = []

    @property
    def spans(self) -> list[dict[str, Any]]:
        """Return the list of exported (sanitized) spans."""
        return list(self._exported)

    def export_span(self, span: dict[str, Any]) -> dict[str, Any]:
        """Filter *span* through the allow-list and record the result.

        Returns the sanitized span (a new dict containing only allowed
        fields).
        """
        sanitized = self._allow_list.filter_span(span)
        self._exported.append(sanitized)
        return sanitized

    def export_spans(self, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter a batch of spans and record each sanitized result."""
        return [self.export_span(s) for s in spans]

    def clear(self) -> None:
        """Forget all exported spans."""
        self._exported.clear()


class TelemetryCanary:
    """Canary secret used to verify that sensitive values are not exported.

    The canary is a fixed, well-known string. Tests inject it into a span
    (simulating an accidental leak), export the span through the allow-list,
    and assert the canary is absent from the exported output. Because the
    canary is placed under a field name that is never on the allow-list
    (``"secret"``), it must be stripped before export.
    """

    #: Fixed canary secret string — a plain literal, not from ``secrets``.
    CANARY_SECRET: Final[str] = "canary-secret-do-not-export-0xdeadbeef"

    #: Field name under which the canary is injected (never allow-listed).
    _CANARY_FIELD: Final[str] = "secret"

    def inject_canary(self, span: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of *span* with the canary secret injected.

        The canary is placed under the ``"secret"`` field name, which is
        never on the default allow-list, so it should be stripped by any
        conforming :class:`TelemetryAllowList`. The input span is not
        mutated.
        """
        leaked = dict(span)
        leaked[self._CANARY_FIELD] = self.CANARY_SECRET
        return leaked

    def check_canary_absent(
        self, exported_spans: list[dict[str, Any]]
    ) -> bool:
        """Return True if the canary secret does NOT appear in *exported_spans*.

        Performs a recursive string search across all values in every
        exported span (including nested dicts/lists).
        """
        return all(not self.scan_for_canary(span) for span in exported_spans)

    def scan_for_canary(self, data: Any) -> bool:
        """Recursively search *data* for the canary secret string.

        Searches strings, dict keys, dict values, list elements, tuples and
        sets. Returns True if the canary appears anywhere in the structure.
        """
        return self._scan(data)

    def _scan(self, data: Any) -> bool:
        if isinstance(data, str):
            return self.CANARY_SECRET in data
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(key, str) and self.CANARY_SECRET in key:
                    return True
                if self._scan(value):
                    return True
            return False
        if isinstance(data, (list, tuple, set, frozenset)):
            return any(self._scan(item) for item in data)
        return False
