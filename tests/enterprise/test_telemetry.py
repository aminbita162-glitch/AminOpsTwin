"""Tests for secure telemetry allow-list and canary (P18, G18.5, Deliverable 5)."""

from __future__ import annotations

from typing import Any

import pytest
from aminopstwin.assurance.telemetry import (
    DEFAULT_TELEMETRY_ALLOWED_FIELDS,
    SENSITIVE_FIELDS,
    TelemetryAllowList,
    TelemetryCanary,
    TelemetryExporter,
    TelemetryField,
    default_telemetry_fields,
)


class TestTelemetryField:
    """TelemetryField frozen dataclass."""

    def test_is_frozen(self) -> None:
        import dataclasses

        f = TelemetryField(name="trace_id", value_type="str")
        with pytest.raises(
            dataclasses.FrozenInstanceError
        ):
            f.name = "other"  # type: ignore[misc]

    def test_defaults_allowed_values_none(self) -> None:
        f = TelemetryField(name="outcome", value_type="str")
        assert f.allowed_values is None

    def test_allowed_values_set(self) -> None:
        f = TelemetryField(
            name="outcome",
            value_type="str",
            allowed_values=["PASS", "FAIL"],
        )
        assert f.allowed_values == ["PASS", "FAIL"]


class TestAllowList:
    """TelemetryAllowList filtering."""

    def test_is_allowed_true_for_allowed(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id", "span_id"})
        assert al.is_allowed("trace_id") is True
        assert al.is_allowed("span_id") is True

    def test_is_allowed_false_for_non_allowed(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id"})
        assert al.is_allowed("secret") is False
        assert al.is_allowed("password") is False

    def test_allowed_fields_property_returns_copy(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id", "span_id"})
        first = al.allowed_fields
        first.add("mutated")
        second = al.allowed_fields
        assert first != second
        assert "mutated" not in second
        assert second == {"trace_id", "span_id"}

    def test_filter_span_keeps_only_allowed(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id", "span_id"})
        span: dict[str, Any] = {
            "trace_id": "abc",
            "span_id": "def",
            "secret": "leak",
            "password": "hunter2",
        }
        filtered = al.filter_span(span)
        assert set(filtered.keys()) == {"trace_id", "span_id"}
        assert filtered["trace_id"] == "abc"
        assert "secret" not in filtered
        assert "password" not in filtered

    def test_filter_span_does_not_mutate_input(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id"})
        span: dict[str, Any] = {"trace_id": "abc", "secret": "leak"}
        _filtered = al.filter_span(span)
        assert "secret" in span
        assert span["secret"] == "leak"

    def test_filter_span_empty_when_nothing_allowed(self) -> None:
        al = TelemetryAllowList(allowed_fields=set())
        span: dict[str, Any] = {"trace_id": "abc", "secret": "leak"}
        assert al.filter_span(span) == {}


class TestExporter:
    """TelemetryExporter sanitizes and retains spans."""

    def test_export_span_returns_sanitized(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id", "span_id"})
        exp = TelemetryExporter(al)
        out = exp.export_span({"trace_id": "t", "span_id": "s", "secret": "x"})
        assert out == {"trace_id": "t", "span_id": "s"}
        assert "secret" not in out

    def test_export_span_recorded_in_spans(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id"})
        exp = TelemetryExporter(al)
        exp.export_span({"trace_id": "t1", "secret": "x1"})
        exp.export_span({"trace_id": "t2", "secret": "x2"})
        assert exp.spans == [{"trace_id": "t1"}, {"trace_id": "t2"}]

    def test_export_spans_batch(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id"})
        exp = TelemetryExporter(al)
        out = exp.export_spans(
            [
                {"trace_id": "t1", "secret": "x1"},
                {"trace_id": "t2", "password": "p2"},
            ]
        )
        assert out == [{"trace_id": "t1"}, {"trace_id": "t2"}]
        assert exp.spans == [{"trace_id": "t1"}, {"trace_id": "t2"}]

    def test_spans_returns_copy(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id"})
        exp = TelemetryExporter(al)
        exp.export_span({"trace_id": "t"})
        snapshot = exp.spans
        snapshot.append({"trace_id": "mutated"})
        assert exp.spans == [{"trace_id": "t"}]

    def test_clear_resets_spans(self) -> None:
        al = TelemetryAllowList(allowed_fields={"trace_id"})
        exp = TelemetryExporter(al)
        exp.export_span({"trace_id": "t"})
        exp.clear()
        assert exp.spans == []


class TestDefaultAllowList:
    """The project default allow-list excludes sensitive fields."""

    def test_default_includes_expected_fields(self) -> None:
        for name in (
            "trace_id",
            "span_id",
            "operation",
            "tenant_id",
            "duration_ms",
            "outcome",
            "timestamp",
        ):
            assert name in DEFAULT_TELEMETRY_ALLOWED_FIELDS

    def test_default_excludes_sensitive_fields(self) -> None:
        for name in ("secret", "password", "token", "api_key", "payload"):
            assert name not in DEFAULT_TELEMETRY_ALLOWED_FIELDS
            assert name in SENSITIVE_FIELDS

    def test_sensitive_fields_disjoint_from_default(self) -> None:
        assert DEFAULT_TELEMETRY_ALLOWED_FIELDS.isdisjoint(SENSITIVE_FIELDS)

    def test_default_telemetry_fields_returns_fresh_set(self) -> None:
        s = default_telemetry_fields()
        s.add("mutated")
        s2 = default_telemetry_fields()
        assert "mutated" not in s2

    def test_default_allow_list_strips_sensitive(self) -> None:
        al = TelemetryAllowList(allowed_fields=default_telemetry_fields())
        span: dict[str, Any] = {
            "trace_id": "t",
            "span_id": "s",
            "operation": "invoke",
            "tenant_id": "tenant-1",
            "duration_ms": 12,
            "outcome": "PASS",
            "timestamp": 1000,
            "secret": "leak",
            "password": "hunter2",
            "token": "tok",
            "api_key": "key",
            "payload": {"data": "x"},
        }
        filtered = al.filter_span(span)
        assert set(filtered.keys()) == {
            "trace_id",
            "span_id",
            "operation",
            "tenant_id",
            "duration_ms",
            "outcome",
            "timestamp",
        }
        for sensitive in ("secret", "password", "token", "api_key", "payload"):
            assert sensitive not in filtered


class TestCanary:
    """TelemetryCanary — the core security test."""

    def _default_exporter(self) -> TelemetryExporter:
        return TelemetryExporter(
            TelemetryAllowList(allowed_fields=default_telemetry_fields())
        )

    def test_canary_secret_is_fixed_literal(self) -> None:
        assert (
            TelemetryCanary.CANARY_SECRET
            == "canary-secret-do-not-export-0xdeadbeef"
        )

    def test_inject_canary_adds_secret_field(self) -> None:
        canary = TelemetryCanary()
        span: dict[str, Any] = {"trace_id": "t"}
        leaked = canary.inject_canary(span)
        assert leaked["secret"] == TelemetryCanary.CANARY_SECRET
        # input not mutated
        assert "secret" not in span

    def test_check_canary_absent_true_for_clean_spans(self) -> None:
        canary = TelemetryCanary()
        spans: list[dict[str, Any]] = [
            {"trace_id": "t", "span_id": "s"},
            {"operation": "invoke"},
        ]
        assert canary.check_canary_absent(spans) is True

    def test_check_canary_absent_false_for_dirty_spans(self) -> None:
        canary = TelemetryCanary()
        spans: list[dict[str, Any]] = [
            {"trace_id": "t", "secret": TelemetryCanary.CANARY_SECRET},
        ]
        assert canary.check_canary_absent(spans) is False

    def test_check_canary_absent_false_when_in_nested_value(self) -> None:
        canary = TelemetryCanary()
        spans: list[dict[str, Any]] = [
            {"trace_id": "t", "attrs": {"note": TelemetryCanary.CANARY_SECRET}},
        ]
        assert canary.check_canary_absent(spans) is False

    def test_check_canary_absent_false_when_in_nested_list(self) -> None:
        canary = TelemetryCanary()
        spans: list[dict[str, Any]] = [
            {"trace_id": "t", "tags": [TelemetryCanary.CANARY_SECRET]},
        ]
        assert canary.check_canary_absent(spans) is False

    def test_scan_for_canary_string(self) -> None:
        canary = TelemetryCanary()
        assert canary.scan_for_canary("plain " + TelemetryCanary.CANARY_SECRET) is True
        assert canary.scan_for_canary("nothing here") is False

    def test_scan_for_canary_nested_dict(self) -> None:
        canary = TelemetryCanary()
        data: Any = {
            "a": {"b": {"c": [TelemetryCanary.CANARY_SECRET]}},
        }
        assert canary.scan_for_canary(data) is True

    def test_scan_for_canary_nested_list(self) -> None:
        canary = TelemetryCanary()
        data: Any = [[{"deep": TelemetryCanary.CANARY_SECRET}]]
        assert canary.scan_for_canary(data) is True

    def test_scan_for_canary_in_key(self) -> None:
        canary = TelemetryCanary()
        data: Any = {TelemetryCanary.CANARY_SECRET: 1}
        assert canary.scan_for_canary(data) is True

    def test_scan_for_canary_tuple(self) -> None:
        canary = TelemetryCanary()
        data: Any = (1, 2, TelemetryCanary.CANARY_SECRET)
        assert canary.scan_for_canary(data) is True

    def test_scan_for_canary_set(self) -> None:
        canary = TelemetryCanary()
        data: Any = {TelemetryCanary.CANARY_SECRET}
        assert canary.scan_for_canary(data) is True

    def test_scan_for_canary_false_for_ints(self) -> None:
        canary = TelemetryCanary()
        data: Any = 12345
        assert canary.scan_for_canary(data) is False

    def test_scan_for_canary_false_for_empty(self) -> None:
        canary = TelemetryCanary()
        assert canary.scan_for_canary(None) is False
        assert canary.scan_for_canary({}) is False
        assert canary.scan_for_canary([]) is False

    # --- the core end-to-end security test -------------------------

    def test_canary_never_appears_in_exported_spans(self) -> None:
        """Inject the canary into a span and export it; the canary must not
        appear anywhere in the exported (allow-listed) output."""
        canary = TelemetryCanary()
        exp = self._default_exporter()
        dirty = canary.inject_canary(
            {
                "trace_id": "t",
                "span_id": "s",
                "operation": "invoke",
                "tenant_id": "tenant-1",
                "duration_ms": 5,
                "outcome": "PASS",
                "timestamp": 1000,
            }
        )
        exported = [exp.export_span(dirty)]
        assert canary.check_canary_absent(exported) is True
        # the canary must not be in the retained spans either
        assert canary.check_canary_absent(exp.spans) is True

    def test_inject_then_export_removes_canary(self) -> None:
        """Injecting then exporting through the allow-list removes the canary."""
        canary = TelemetryCanary()
        exp = self._default_exporter()
        original: dict[str, Any] = {
            "trace_id": "t",
            "span_id": "s",
            "timestamp": 1,
        }
        leaked = canary.inject_canary(original)
        out = exp.export_span(leaked)
        assert "secret" not in out
        assert TelemetryCanary.CANARY_SECRET not in str(out)
        assert canary.scan_for_canary(out) is False

    def test_batch_export_strips_canary_from_all(self) -> None:
        canary = TelemetryCanary()
        exp = self._default_exporter()
        spans = [
            canary.inject_canary({"trace_id": "t1", "timestamp": 1}),
            canary.inject_canary({"trace_id": "t2", "timestamp": 2}),
        ]
        exported = exp.export_spans(spans)
        assert canary.check_canary_absent(exported) is True
        for s in exported:
            assert "secret" not in s
