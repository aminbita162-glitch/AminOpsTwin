"""Tests for raw JSON ingestion at the API edge (P12, G12.1).

G12.1: raw JSON rejects duplicate keys and floats with exact reason
codes.
"""

from __future__ import annotations

import pytest
from aminopstwin.gateway.raw_json import (
    R_DUPLICATE_KEY,
    R_FLOAT,
    R_INFINITY,
    R_MALFORMED,
    R_NAN,
    R_NEG_INFINITY,
    RawJsonError,
    parse_raw_json,
)


class TestParseRawJson:
    """parse_raw_json — valid inputs."""

    def test_simple_object(self) -> None:
        result = parse_raw_json(b'{"a": 1, "b": "hello"}')
        assert result == {"a": 1, "b": "hello"}

    def test_nested_object(self) -> None:
        result = parse_raw_json(b'{"outer": {"inner": [1, 2, true]}}')
        assert result == {"outer": {"inner": [1, 2, True]}}

    def test_null_and_bool(self) -> None:
        result = parse_raw_json(b'{"x": null, "y": true, "z": false}')
        assert result == {"x": None, "y": True, "z": False}

    def test_string_input(self) -> None:
        result = parse_raw_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_large_integer(self) -> None:
        result = parse_raw_json(b'{"big": 9007199254740991}')
        assert result == {"big": 9007199254740991}

    def test_negative_integer(self) -> None:
        result = parse_raw_json(b'{"neg": -42}')
        assert result == {"neg": -42}

    def test_empty_object(self) -> None:
        result = parse_raw_json(b'{}')
        assert result == {}

    def test_list_in_object(self) -> None:
        result = parse_raw_json(b'{"items": [1, 2, 3]}')
        assert result == {"items": [1, 2, 3]}


class TestRejectFloat:
    """parse_raw_json — float rejection with exact code GW-INJ-004."""

    def test_simple_float(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"x": 1.5}')
        assert exc_info.value.reason_code == R_FLOAT

    def test_float_zero(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"x": 0.0}')
        assert exc_info.value.reason_code == R_FLOAT

    def test_exponential_notation(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"x": 1e3}')
        assert exc_info.value.reason_code == R_FLOAT

    def test_negative_exponential(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"x": 1.5e-2}')
        assert exc_info.value.reason_code == R_FLOAT

    def test_float_in_nested(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"outer": {"inner": 3.14}}')
        assert exc_info.value.reason_code == R_FLOAT

    def test_float_in_list(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"items": [1, 2.5, 3]}')
        assert exc_info.value.reason_code == R_FLOAT


class TestRejectNaN:
    """parse_raw_json — NaN rejection with exact code GW-INJ-005."""

    def test_nan(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"x": NaN}')
        assert exc_info.value.reason_code == R_NAN


class TestRejectInfinity:
    """parse_raw_json — Infinity / -Infinity rejection."""

    def test_infinity(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"x": Infinity}')
        assert exc_info.value.reason_code == R_INFINITY

    def test_neg_infinity(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"x": -Infinity}')
        assert exc_info.value.reason_code == R_NEG_INFINITY


class TestRejectDuplicateKeys:
    """parse_raw_json — duplicate key rejection with exact code GW-INJ-003."""

    def test_simple_duplicate(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"a": 1, "a": 2}')
        assert exc_info.value.reason_code == R_DUPLICATE_KEY

    def test_nested_duplicate(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"outer": {"a": 1, "a": 2}}')
        assert exc_info.value.reason_code == R_DUPLICATE_KEY

    def test_duplicate_in_nested_list(self) -> None:
        body = b'{"items": [{"a": 1, "a": 2}]}'
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(body)
        assert exc_info.value.reason_code == R_DUPLICATE_KEY

    def test_no_duplicate_error_when_keys_differ(self) -> None:
        result = parse_raw_json(b'{"a": 1, "b": 2, "c": 3}')
        assert result == {"a": 1, "b": 2, "c": 3}


class TestRejectMalformed:
    """parse_raw_json — malformed JSON rejection with exact code GW-INJ-008."""

    def test_trailing_comma(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"a": 1,}')
        assert exc_info.value.reason_code == R_MALFORMED

    def test_missing_brace(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'{"a": 1')
        assert exc_info.value.reason_code == R_MALFORMED

    def test_empty_body(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'')
        assert exc_info.value.reason_code == R_MALFORMED

    def test_non_utf8(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'\xff\xfe')
        assert exc_info.value.reason_code == R_MALFORMED

    def test_top_level_array(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'[1, 2, 3]')
        assert exc_info.value.reason_code == R_MALFORMED

    def test_top_level_string(self) -> None:
        with pytest.raises(RawJsonError) as exc_info:
            parse_raw_json(b'"hello"')
        assert exc_info.value.reason_code == R_MALFORMED


class TestDeterminism:
    """parse_raw_json — same bytes always produce same result or rejection."""

    def test_same_bytes_same_result(self) -> None:
        raw = b'{"a": 1, "b": [1, 2, true]}'
        r1 = parse_raw_json(raw)
        r2 = parse_raw_json(raw)
        assert r1 == r2

    def test_same_bytes_same_rejection(self) -> None:
        raw = b'{"a": 1, "a": 2}'
        codes: list[str] = []
        for _ in range(2):
            with pytest.raises(RawJsonError) as exc_info:
                parse_raw_json(raw)
            codes.append(exc_info.value.reason_code)
        assert codes[0] == codes[1]
