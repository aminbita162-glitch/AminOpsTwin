"""LLM Adapter tests — record/replay with zero live calls (G2.10).

Tests:
    - Record/replay: a recording is loaded and replayed correctly
    - Replay miss raises ReplayMissError (G2.10)
    - 0 live network calls in the test suite
    - Request hash determinism
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

import pytest
from aminopstwin.contracts.clock import SeededClock
from aminopstwin.tokens.llm_adapter import LLMAdapter, LLMRecord, ReplayMissError


class TestLLMRecordReplay:
    """Record/replay: a recording is loaded and replayed correctly."""

    def test_record_and_replay(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
        )
        adapter = LLMAdapter(
            adapter_version="test-v1",
            model_id="test-model",
        )
        messages = [{"role": "user", "content": "Hello"}]
        params = {"temperature": 0, "max_tokens": 100}

        record = adapter.add_recording(
            messages=messages,
            params=params,
            schema_id="ops.sim.scenario@1",
            response="World",
            tokens_input=5,
            tokens_output=1,
            clock=clock,
        )
        assert isinstance(record, LLMRecord)
        assert record.response == "World"
        assert record.tokens_input == 5
        assert record.tokens_output == 1

        # Replay the same request
        response, replayed = adapter.call(
            messages=messages,
            params=params,
            schema_id="ops.sim.scenario@1",
            clock=clock,
        )
        assert response == "World"
        assert replayed.response == "World"
        assert replayed.request_hash == record.request_hash

    def test_replay_returns_same_record(self) -> None:
        clock = SeededClock()
        adapter = LLMAdapter("v1", "m1")
        messages = [{"role": "user", "content": "test"}]
        params = {"temperature": 0}

        original = adapter.add_recording(
            messages=messages,
            params=params,
            schema_id="schema@1",
            response="reply",
            tokens_input=4,
            tokens_output=1,
            clock=clock,
        )

        _, replayed = adapter.call(
            messages=messages,
            params=params,
            schema_id="schema@1",
            clock=clock,
        )
        assert replayed.request_hash == original.request_hash
        assert replayed.response_hash == original.response_hash


class TestReplayMiss:
    """Replay miss raises ReplayMissError (G2.10)."""

    def test_replay_miss_raises(self) -> None:
        clock = SeededClock()
        adapter = LLMAdapter("v1", "m1")
        messages = [{"role": "user", "content": "unknown"}]
        params = {"temperature": 0}

        with pytest.raises(ReplayMissError):
            adapter.call(
                messages=messages,
                params=params,
                schema_id="schema@1",
                clock=clock,
            )

    def test_replay_miss_no_live_call(self) -> None:
        """The adapter never falls through to a live network call."""
        clock = SeededClock()
        adapter = LLMAdapter("v1", "m1")
        # No recordings loaded at all
        assert len(adapter._recordings) == 0
        with pytest.raises(ReplayMissError):
            adapter.call(
                messages=[{"role": "user", "content": "anything"}],
                params={},
                schema_id="schema@1",
                clock=clock,
            )

    def test_different_params_different_hash(self) -> None:
        """Different params produce different request hashes -> replay miss."""
        clock = SeededClock()
        adapter = LLMAdapter("v1", "m1")
        messages = [{"role": "user", "content": "hello"}]
        params1 = {"temperature": 0, "max_tokens": 100}
        params2 = {"temperature": 1, "max_tokens": 100}

        adapter.add_recording(
            messages=messages,
            params=params1,
            schema_id="schema@1",
            response="cold",
            tokens_input=5,
            tokens_output=1,
            clock=clock,
        )

        # Same messages but different params -> different hash -> miss
        with pytest.raises(ReplayMissError):
            adapter.call(
                messages=messages,
                params=params2,
                schema_id="schema@1",
                clock=clock,
            )


class TestRequestHashDeterminism:
    """Request hash determinism — same inputs produce same hash."""

    def test_same_inputs_same_hash(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        params = {"temperature": 0, "max_tokens": 100}

        h1 = LLMAdapter.compute_request_hash("v1", "m1", params, messages)
        h2 = LLMAdapter.compute_request_hash("v1", "m1", params, messages)
        assert h1 == h2
        assert len(h1) == 64
        int(h1, 16)  # valid hex

    def test_different_messages_different_hash(self) -> None:
        params = {"temperature": 0}
        m1 = [{"role": "user", "content": "hello"}]
        m2 = [{"role": "user", "content": "world"}]

        h1 = LLMAdapter.compute_request_hash("v1", "m1", params, m1)
        h2 = LLMAdapter.compute_request_hash("v1", "m1", params, m2)
        assert h1 != h2

    def test_different_model_different_hash(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        params = {"temperature": 0}

        h1 = LLMAdapter.compute_request_hash("v1", "m1", params, messages)
        h2 = LLMAdapter.compute_request_hash("v1", "m2", params, messages)
        assert h1 != h2

    def test_different_adapter_version_different_hash(self) -> None:
        messages = [{"role": "user", "content": "hello"}]
        params = {"temperature": 0}

        h1 = LLMAdapter.compute_request_hash("v1", "m1", params, messages)
        h2 = LLMAdapter.compute_request_hash("v2", "m1", params, messages)
        assert h1 != h2

    def test_param_order_independent(self) -> None:
        """Key ordering in params dict should not affect the hash
        because compute_request_hash uses sort_keys=True."""
        messages = [{"role": "user", "content": "hello"}]
        params1 = {"temperature": 0, "max_tokens": 100}
        params2 = {"max_tokens": 100, "temperature": 0}

        h1 = LLMAdapter.compute_request_hash("v1", "m1", params1, messages)
        h2 = LLMAdapter.compute_request_hash("v1", "m1", params2, messages)
        assert h1 == h2


class TestRecordingsFromDir:
    """Recordings loaded from a directory."""

    def test_load_from_dir(self, tmp_path: Path) -> None:
        clock = SeededClock()
        adapter = LLMAdapter("v1", "m1")
        messages = [{"role": "user", "content": "test"}]
        params = {"temperature": 0}

        record = adapter.add_recording(
            messages=messages,
            params=params,
            schema_id="schema@1",
            response="reply",
            tokens_input=4,
            tokens_output=1,
            clock=clock,
        )

        # Write recording to a file
        rec_path = tmp_path / f"{record.request_hash}.json"
        rec_path.write_text(json.dumps(record.model_dump(mode="json")))

        # Load from dir
        adapter2 = LLMAdapter("v1", "m1", recordings_dir=tmp_path)
        response, replayed = adapter2.call(
            messages=messages,
            params=params,
            schema_id="schema@1",
            clock=clock,
        )
        assert response == "reply"
        assert replayed.request_hash == record.request_hash


class TestLLMRecordFrozen:
    """LLMRecord is frozen and strict."""

    def test_record_frozen(self) -> None:
        from pydantic import ValidationError

        record = LLMRecord(
            record_id="rec-001",
            request_hash="a" * 64,
            response="test",
            response_hash="b" * 64,
            model_id="m1",
            adapter_version="v1",
            expected_schema_id="schema@1",
            tokens_input=10,
            tokens_output=5,
            recorded_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        with pytest.raises(ValidationError):
            record.response = "tampered"  # type: ignore[misc]

    def test_negative_tokens_rejected(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            LLMRecord(
                record_id="rec-002",
                request_hash="a" * 64,
                response="test",
                response_hash="b" * 64,
                model_id="m1",
                adapter_version="v1",
                expected_schema_id="schema@1",
                tokens_input=-1,
                tokens_output=0,
                recorded_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
            )

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError):
            LLMRecord(
                record_id="rec-003",
                request_hash="a" * 64,
                response="test",
                response_hash="b" * 64,
                model_id="m1",
                adapter_version="v1",
                expected_schema_id="schema@1",
                tokens_input=0,
                tokens_output=0,
                recorded_at=_dt.datetime(2026, 1, 1),  # naive
            )


def test_zero_live_network_calls() -> None:
    """G2.10: The LLM adapter test suite makes zero live network calls.

    This test asserts that the adapter has no httpx, requests, or
    openai imports — it is pure record/replay.
    """
    import aminopstwin.tokens.llm_adapter as mod

    source = Path(mod.__file__).read_text()
    forbidden = ["import httpx", "import requests", "import openai",
                 "import aiohttp", "import urllib"]
    for fb in forbidden:
        assert fb not in source, f"forbidden import found: {fb}"
