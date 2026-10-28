"""Tests for P26: new reason codes are registered.

GW-IDEMP-001, GW-IDEMP-002, GW-REVOKE-001, GW-UNK-001 to GW-UNK-005.
"""

from __future__ import annotations

from aminopstwin.contracts.reasons import is_known_code


class TestReasonCodesRegistered:
    """Verify all P26 reason codes are in the registry."""

    def test_gw_idemp_001_registered(self) -> None:
        assert is_known_code("GW-IDEMP-001")

    def test_gw_idemp_002_registered(self) -> None:
        assert is_known_code("GW-IDEMP-002")

    def test_gw_revoke_001_registered(self) -> None:
        assert is_known_code("GW-REVOKE-001")

    def test_gw_unk_001_registered(self) -> None:
        assert is_known_code("GW-UNK-001")

    def test_gw_unk_002_registered(self) -> None:
        assert is_known_code("GW-UNK-002")

    def test_gw_unk_003_registered(self) -> None:
        assert is_known_code("GW-UNK-003")

    def test_gw_unk_004_registered(self) -> None:
        assert is_known_code("GW-UNK-004")

    def test_gw_unk_005_registered(self) -> None:
        assert is_known_code("GW-UNK-005")
