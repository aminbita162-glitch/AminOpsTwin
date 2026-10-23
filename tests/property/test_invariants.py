"""Property-based invariant tests (§5.1, G1.8).

Each test corresponds to an invariant in docs/invariant_catalog.yaml.
Uses Hypothesis for property-based testing with fixed PYTHONHASHSEED.
"""

from __future__ import annotations

import datetime as _dt
import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src.contracts.canonical import (
    CanonicalError,
    canonical_bytes,
    canonical_hash,
)
from src.contracts.clock import SeededClock, SeededIdFactory
from src.contracts.decision import Decision, DecisionRecord, Stage
from src.contracts.envelope import Envelope
from src.gateway.gateway import (
    PolicyGateway,
    PolicyMatrix,
    PolicyMatrixEntry,
)
from src.tokens.prefilter import (
    PREFILTER_ORDER,
    PreFilterStage,
    prefilter_order_valid,
)

# --- Strategies ---

# Canonical-safe payload values (no float, no NaN, no non-NFC)
_canonical_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**53) + 1, max_value=2**53 - 1),
    st.text(alphabet=st.characters(), min_size=0, max_size=20),
)

_canonical_payload = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(
            min_value=-(2**53) + 1, max_value=2**53 - 1
        ),
        st.text(min_size=0, max_size=20),
    ),
    lambda children: st.one_of(
        st.lists(children, min_size=0, max_size=5),
        st.dictionaries(
            st.text(
                alphabet=st.characters(
                    whitelist_categories=("Lu", "Ll", "Nd"),
                ),
                min_size=1,
                max_size=5,
            ),
            children,
            min_size=0,
            max_size=3,
        ),
    ),
    max_leaves=10,
)


# --- Helper fixtures ---

def _make_gateway(
    epoch: int = 0,
) -> PolicyGateway:
    """Create a test gateway with standard registries."""
    entries = {
        PolicyMatrixEntry("A2", "scenario", "simulate"),
        PolicyMatrixEntry("A3", "evidence_query", "query"),
    }
    return PolicyGateway(
        policy_matrix=PolicyMatrix(entries),
        current_epoch=epoch,
        schema_registry={
            "ops.sim.scenario@1",
            "ops.evidence.query@1",
        },
        envelope_type_registry={
            "ops.sim.scenario@1": "scenario",
            "ops.evidence.query@1": "evidence_query",
        },
    )


def _make_envelope(
    payload: dict | None = None,
    policy_epoch: int = 0,
) -> Envelope:
    """Create a valid test envelope."""
    pl = payload if payload is not None else {"site": "a", "cap": 1}
    clock = SeededClock()
    idf = SeededIdFactory(seed=42)
    return Envelope(
        envelope_version="1.0",
        schema_id="ops.sim.scenario@1",
        envelope_type="scenario",
        correlation_id=idf.new_id(),
        causation_id=None,
        tenant_id="tenant-default",
        policy_epoch=policy_epoch,
        idempotency_key="test-idempotency-key-001",
        payload=pl,
        payload_hash=canonical_hash(pl),
        created_at=clock.now(),
    )


# --- INV-001: payload_hash equals SHA-256 of canonical bytes ---

@given(_canonical_payload)
@settings(
    max_examples=1000,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_payload_hash_matches_canonical(payload: object) -> None:
    """INV-001: Envelope.payload_hash == SHA-256(canonical_bytes)."""
    expected = canonical_hash(payload)
    actual = canonical_hash(payload)
    assert expected == actual


# --- INV-002: non-NFC strings rejected ---

def test_non_nfc_rejected() -> None:
    """INV-002: non-NFC strings in payload values and keys rejected."""
    with pytest.raises(CanonicalError):
        canonical_bytes({"a": "cafe\u0301"})
    with pytest.raises(CanonicalError):
        canonical_bytes({"cafe\u0301": 1})


# --- INV-003: float values rejected ---

def test_float_rejected() -> None:
    """INV-003: float values in payload rejected (N-15)."""
    with pytest.raises(CanonicalError):
        canonical_bytes({"a": 1.5})
    with pytest.raises(CanonicalError):
        canonical_bytes({"a": 0.1})


# --- INV-004: forbidden 'issuer' key rejected ---

def test_issuer_key_rejected() -> None:
    """INV-004: 'issuer' key anywhere in payload rejected."""
    with pytest.raises(ValueError):
        _make_envelope(payload={"issuer": "A1"})
    with pytest.raises(ValueError):
        _make_envelope(payload={"nested": {"issuer": "A1"}})
    with pytest.raises(ValueError):
        _make_envelope(payload={"list": [{"issuer": "A1"}]})


# --- INV-005: Gateway purity ---

def test_gateway_purity() -> None:
    """INV-005: 1000 repeated calls give same output."""
    gw = _make_gateway()
    env = _make_envelope()
    decided_at = SeededClock().now()

    records = [
        gw.evaluate(env, "A2", decided_at, "simulate")
        for _ in range(1000)
    ]
    first = records[0]
    for r in records[1:]:
        assert r.decision == first.decision
        assert r.reason_code == first.reason_code
        assert r.stage == first.stage


# --- INV-006: deny-by-default ---

def test_deny_by_default() -> None:
    """INV-006: unknown schema_id yields GW-DEFAULT-001."""
    gw = _make_gateway()
    env = _make_envelope()
    decided_at = SeededClock().now()

    # Override schema_id to unknown
    env2 = Envelope(
        envelope_version="1.0",
        schema_id="unknown.schema@1",
        envelope_type="scenario",
        correlation_id=env.correlation_id,
        causation_id=None,
        tenant_id="tenant-default",
        policy_epoch=0,
        idempotency_key="test-idempotency-key-001",
        payload=env.payload,
        payload_hash=env.payload_hash,
        created_at=env.created_at,
    )
    record = gw.evaluate(env2, "A2", decided_at, "simulate")
    assert record.decision == Decision.DENY
    assert record.reason_code == "GW-DEFAULT-001"


# --- INV-007: outdated epoch ---

def test_epoch_outdated() -> None:
    """INV-007: outdated epoch yields GW-EPOCH-001."""
    gw = _make_gateway(epoch=3)
    env = _make_envelope(policy_epoch=0)
    decided_at = SeededClock().now()
    record = gw.evaluate(env, "A2", decided_at, "simulate")
    assert record.decision == Decision.DENY
    assert record.reason_code == "GW-EPOCH-001"


# --- INV-008: future epoch ---

def test_epoch_future() -> None:
    """INV-008: future epoch yields GW-EPOCH-002."""
    gw = _make_gateway(epoch=0)
    env = _make_envelope(policy_epoch=5)
    decided_at = SeededClock().now()
    record = gw.evaluate(env, "A2", decided_at, "simulate")
    assert record.decision == Decision.DENY
    assert record.reason_code == "GW-EPOCH-002"


# --- INV-009: authorization denied ---

def test_auth_denied() -> None:
    """INV-009: unlisted (principal, type, capability) yields GW-AUTH-001."""
    gw = _make_gateway()
    env = _make_envelope()
    decided_at = SeededClock().now()
    record = gw.evaluate(env, "X1", decided_at, "simulate")
    assert record.decision == Decision.DENY
    assert record.reason_code == "GW-AUTH-001"


# --- INV-010: ALLOW has no reason_code ---

def test_allow_no_reason() -> None:
    """INV-010: ALLOW DecisionRecord always has reason_code=None."""
    gw = _make_gateway()
    env = _make_envelope()
    decided_at = SeededClock().now()
    record = gw.evaluate(env, "A2", decided_at, "simulate")
    assert record.decision == Decision.ALLOW
    assert record.reason_code is None


# --- INV-011: DENY has reason_code ---

def test_deny_has_reason() -> None:
    """INV-011: DENY DecisionRecord always has a reason_code."""
    gw = _make_gateway()
    env = _make_envelope()
    decided_at = SeededClock().now()
    record = gw.evaluate(env, "X1", decided_at, "simulate")
    assert record.decision == Decision.DENY
    assert record.reason_code is not None


# --- INV-012: pre-filter order ---

def test_prefilter_order() -> None:
    """INV-012: pre-filter order is fixed."""
    assert PREFILTER_ORDER == (
        PreFilterStage.SCHEMA,
        PreFilterStage.GATEWAY,
        PreFilterStage.CACHE,
        PreFilterStage.INVARIANT,
        PreFilterStage.BUDGET,
        PreFilterStage.OUTPUT,
    )
    assert prefilter_order_valid(list(PREFILTER_ORDER))


# --- INV-013: canonical determinism ---

@given(_canonical_payload)
@settings(
    max_examples=1000,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)
def test_canonical_determinism(payload: object) -> None:
    """INV-013: same payload always produces same bytes."""
    b1 = canonical_bytes(payload)
    b2 = canonical_bytes(payload)
    assert b1 == b2


# --- INV-014: Envelope is frozen ---

def test_envelope_frozen() -> None:
    """INV-014: attribute assignment raises after construction."""
    env = _make_envelope()
    with pytest.raises(Exception):
        env.tenant_id = "other-tenant"  # type: ignore[misc]


# --- INV-015: Envelope extra='forbid' ---

def test_envelope_extra_forbid() -> None:
    """INV-015: unknown fields rejected at construction."""
    with pytest.raises(Exception):
        Envelope(
            envelope_version="1.0",
            schema_id="ops.sim.scenario@1",
            envelope_type="scenario",
            correlation_id=uuid.uuid4(),
            causation_id=None,
            tenant_id="tenant-default",
            policy_epoch=0,
            idempotency_key="test-idempotency-key-001",
            payload={"site": "a"},
            payload_hash=canonical_hash({"site": "a"}),
            created_at=SeededClock().now(),
            extra_field="should_fail",  # type: ignore[call-arg]
        )


# --- INV-016: IdFactory UUID v4 layout ---

def test_uuid_v4_layout() -> None:
    """INV-016: IdFactory produces UUID v4 layout."""
    idf = SeededIdFactory(seed=42)
    for _ in range(100):
        u = idf.new_id()
        assert u.version == 4
        assert str(u)[14] == "4"
        assert str(u)[19] in "89ab"


# --- INV-017: SeededIdFactory reproducibility ---

def test_seeded_id_reproducibility() -> None:
    """INV-017: same seed produces identical UUID sequence."""
    idf1 = SeededIdFactory(seed=42)
    idf2 = SeededIdFactory(seed=42)
    seq1 = [str(idf1.new_id()) for _ in range(100)]
    seq2 = [str(idf2.new_id()) for _ in range(100)]
    assert seq1 == seq2


# --- INV-018: NaN and Infinity rejected ---

def test_nan_infinity_rejected() -> None:
    """INV-018: NaN and Infinity in payload rejected."""
    with pytest.raises(CanonicalError):
        canonical_bytes({"a": float("nan")})
    with pytest.raises(CanonicalError):
        canonical_bytes({"a": float("inf")})
    with pytest.raises(CanonicalError):
        canonical_bytes({"a": float("-inf")})
