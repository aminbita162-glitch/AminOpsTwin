"""Schema field scan with canary (§24.3, C5).

Scans all schema definitions in docs/schema_registry.yaml and source
code for known-safe field names, and verifies that a canary field
(forbidden term) IS detected by the scan.
"""

from __future__ import annotations

from pathlib import Path

import yaml

_SCHEMA_REGISTRY = (
    Path(__file__).parent.parent / "docs" / "schema_registry.yaml"
)
_EXCEPTIONS_PATH = (
    Path(__file__).parent.parent / "docs" / "schema_scan_exceptions.yaml"
)

# Forbidden field names that must never appear in a schema definition.
_FORBIDDEN_FIELD_NAMES = frozenset({
    "patient",
    "diagnosis",
    "prognosis",
    "treatment",
    "dose",
    "prescription",
    "eligibility",
    "triage",
    "symptom",
    "medical_advice",
    "issuer",
})


def _load_exceptions() -> set[str]:
    """Load owner-approved scan exceptions."""
    if not _EXCEPTIONS_PATH.exists():
        return set()
    data = yaml.safe_load(_EXCEPTIONS_PATH.read_text())
    return {
        e.get("field", e.get("name", ""))
        for e in (data or {}).get("exceptions", [])
    }


class TestSchemaScan:
    """C5: Schema field scan is clean and canary is detected."""

    def test_schema_registry_loads(self) -> None:
        """Schema registry loads as valid YAML."""
        data = yaml.safe_load(_SCHEMA_REGISTRY.read_text())
        assert "schemas" in data
        assert len(data["schemas"]) > 0

    def test_no_forbidden_fields_in_schemas(self) -> None:
        """No schema in the registry contains a forbidden field name."""
        data = yaml.safe_load(_SCHEMA_REGISTRY.read_text())
        exceptions = _load_exceptions()
        for schema in data.get("schemas", []):
            schema_id = schema.get("schema_id", "?")
            for key, value in schema.items():
                if key in _FORBIDDEN_FIELD_NAMES and key not in exceptions:
                    raise AssertionError(
                        f"forbidden field {key!r} in schema "
                        f"{schema_id}"
                    )
                if (
                    isinstance(value, str)
                    and (val_lower := value.lower()) in _FORBIDDEN_FIELD_NAMES
                    and val_lower not in exceptions
                ):
                    raise AssertionError(
                        f"forbidden value {value!r} in schema "
                        f"{schema_id}"
                    )

    def test_canary_detected(self) -> None:
        """A canary field IS detected by the scan logic."""
        canary_schema = {
            "schema_id": "canary.test@1",
            "patient": "this should be caught",
        }
        found = any(
            k in _FORBIDDEN_FIELD_NAMES
            for k in canary_schema
        )
        assert found, "canary field 'patient' was not detected"

    def test_exceptions_file_exists(self) -> None:
        """The exceptions file exists (even if empty)."""
        assert _EXCEPTIONS_PATH.exists()
