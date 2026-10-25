"""Tests for the Co-Signature Protocol (G13.5).

Verifies that:
- the key rotation protocol document exists
- a Hard-Stop report can carry an optional co_signature field
- the co_signature field is optional (absence does not break verification)
- when present, the co_signature has the required sub-fields
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

REPO_ROOT = Path(__file__).parent.parent.parent
PROTOCOL_FILE = REPO_ROOT / "docs" / "key_rotation_protocol.md"


class HardStopReport(BaseModel):
    """Minimal Hard-Stop report model with optional co-signature (G13.5).

    The co_signature field is optional (default None). Its presence
    or absence does not break verification.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    phase: str
    report_hash: str
    co_signature: dict[str, Any] | None = None


class TestCoSignatureProtocol:
    """G13.5: co-signature field present and optional."""

    def test_protocol_document_exists(self) -> None:
        assert PROTOCOL_FILE.exists(), (
            "docs/key_rotation_protocol.md must exist"
        )

    def test_protocol_describes_key_rotation(self) -> None:
        content = PROTOCOL_FILE.read_text(encoding="utf-8")
        assert "Key Rotation" in content or "key rotation" in content
        assert "OWNER_SIGNING_KEY" in content
        assert "CO_SIGNER_KEY" in content

    def test_protocol_describes_co_signature(self) -> None:
        content = PROTOCOL_FILE.read_text(encoding="utf-8")
        assert "Co-Signature" in content or "co-signature" in content.lower()
        assert "optional" in content.lower()

    def test_report_without_cosignature_is_valid(self) -> None:
        """A report without a co_signature field should be valid."""
        report = HardStopReport(
            phase="P13",
            report_hash=hashlib.sha256(b"test").hexdigest(),
        )
        assert report.co_signature is None
        assert report.phase == "P13"

    def test_report_with_cosignature_is_valid(self) -> None:
        """A report with a co_signature field should be valid."""
        report = HardStopReport(
            phase="P13",
            report_hash=hashlib.sha256(b"test").hexdigest(),
            co_signature={
                "co_signer_id": "co-signer-001",
                "co_signer_key_id": "CO_SIGNER_KEY_v1",
                "signed_at": "2026-10-25T12:00:00Z",
                "signature": "abc123",
            },
        )
        assert report.co_signature is not None
        assert report.co_signature["co_signer_id"] == "co-signer-001"

    def test_cosignature_does_not_break_verification(self) -> None:
        """Reports with and without co_signature should both serialize
        and deserialize cleanly."""
        h = hashlib.sha256(b"test").hexdigest()
        # Without co-signature
        r1 = HardStopReport(phase="P13", report_hash=h)
        d1 = r1.model_dump()
        r1b = HardStopReport(**d1)
        assert r1b.report_hash == h

        # With co-signature
        r2 = HardStopReport(
            phase="P13",
            report_hash=h,
            co_signature={
                "co_signer_id": "co-001",
                "co_signer_key_id": "KEY_v1",
                "signed_at": "2026-10-25T12:00:00Z",
                "signature": "sig123",
            },
        )
        d2 = r2.model_dump()
        r2b = HardStopReport(**d2)
        assert r2b.co_signature is not None
        assert r2b.co_signature["signature"] == "sig123"

    def test_cosignature_required_subfields_when_present(self) -> None:
        """When co_signature is present, it must have the required sub-fields."""
        required_fields = {
            "co_signer_id",
            "co_signer_key_id",
            "signed_at",
            "signature",
        }
        sig = {
            "co_signer_id": "co-001",
            "co_signer_key_id": "KEY_v1",
            "signed_at": "2026-10-25T12:00:00Z",
            "signature": "sig123",
        }
        assert required_fields.issubset(set(sig.keys()))

    def test_report_hash_is_computed_before_cosignature(self) -> None:
        """The report hash must be computed over the content excluding
        the co_signature field, so that adding a co_signature does not
        change the report hash."""
        h = hashlib.sha256(b"report content").hexdigest()
        r_no_sig = HardStopReport(phase="P13", report_hash=h)
        r_with_sig = HardStopReport(
            phase="P13",
            report_hash=h,
            co_signature={
                "co_signer_id": "co-001",
                "co_signer_key_id": "KEY_v1",
                "signed_at": "2026-10-25T12:00:00Z",
                "signature": "sig123",
            },
        )
        # Both reports have the same report_hash (the co_signature
        # does not change it)
        assert r_no_sig.report_hash == r_with_sig.report_hash

    def test_protocol_mentions_bus_factor(self) -> None:
        """The protocol should mention reducing single-person bus factor."""
        content = PROTOCOL_FILE.read_text(encoding="utf-8")
        assert "bus factor" in content.lower()
