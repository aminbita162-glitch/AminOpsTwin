"""G6.7 — Release notes list every capability with its REAL status.

Verifies that docs/release_notes.md:
- Contains the STATUS: CANDIDATE heading
- Contains the honesty sentence
- Lists all 60 capabilities (R01-R30, N01-N30)
- No capability is marked VERIFIED_CANDIDATE
- Every capability has a status line (IMPLEMENTED or ENFORCED)
"""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
RELEASE_NOTES = _ROOT / "docs" / "release_notes.md"
CATALOG = _ROOT / "docs" / "capability_catalog.yaml"
HONESTY_FILE = (
    _ROOT / "docs" / "readme_honesty_sentence.txt"
)


def _load_catalog_ids() -> list[str]:
    """Load all capability IDs from the catalog."""
    text = CATALOG.read_text(encoding="utf-8")
    return re.findall(r"^- id: (\S+)", text, re.MULTILINE)


class TestReleaseNotes:
    """G6.7: Release notes list every capability with its REAL status."""

    def test_release_notes_file_exists(self) -> None:
        """The release notes file exists at docs/release_notes.md."""
        assert RELEASE_NOTES.exists(), (
            f"Release notes not found at {RELEASE_NOTES}"
        )

    def test_status_candidate_heading(self) -> None:
        """Release notes contain the STATUS: CANDIDATE heading."""
        text = RELEASE_NOTES.read_text(encoding="utf-8")
        assert "STATUS: CANDIDATE" in text, (
            "Release notes missing STATUS: CANDIDATE heading"
        )

    def test_honesty_sentence_present(self) -> None:
        """Release notes contain the exact honesty sentence."""
        notes_text = RELEASE_NOTES.read_text(encoding="utf-8")
        honesty_text = HONESTY_FILE.read_text(
            encoding="utf-8"
        ).strip()
        assert honesty_text in notes_text, (
            f"Release notes missing the honesty sentence: "
            f"{honesty_text!r}"
        )

    def test_all_capabilities_listed(self) -> None:
        """Every capability ID from the catalog appears in the notes."""
        catalog_ids = _load_catalog_ids()
        notes_text = RELEASE_NOTES.read_text(encoding="utf-8")
        missing = [
            cid for cid in catalog_ids if cid not in notes_text
        ]
        assert not missing, (
            f"Release notes missing capabilities: {missing}"
        )

    def test_no_verified_candidate_claims(self) -> None:
        """No capability claims VERIFIED_CANDIDATE status."""
        notes_text = RELEASE_NOTES.read_text(encoding="utf-8")
        assert "VERIFIED_CANDIDATE" not in notes_text, (
            "Release notes contain VERIFIED_CANDIDATE — no capability"
            " has owner-verified evidence; all remain"
            " IMPLEMENTED/ENFORCED (CANDIDATE)"
        )

    def test_capability_count(self) -> None:
        """Release notes list all 60 capabilities."""
        catalog_ids = _load_catalog_ids()
        assert len(catalog_ids) == 60, (
            f"Expected 60 capabilities, found {len(catalog_ids)}"
        )
        notes_text = RELEASE_NOTES.read_text(encoding="utf-8")
        for cid in catalog_ids:
            assert f"| {cid} " in notes_text, (
                f"Capability {cid} not in release notes table"
            )

    def test_all_have_status(self) -> None:
        """Every capability row has a status (IMPLEMENTED or ENFORCED)."""
        notes_text = RELEASE_NOTES.read_text(encoding="utf-8")
        catalog_ids = _load_catalog_ids()
        status_re = r"(IMPLEMENTED|ENFORCED) \(CANDIDATE\)"
        for cid in catalog_ids:
            pattern = (
                rf"\| {re.escape(cid)} \|.*\| {status_re} \|"
            )
            assert re.search(pattern, notes_text), (
                f"Capability {cid} row missing status"
            )

    def test_no_production_ready_claims(self) -> None:
        """Release notes do not claim production-ready status (N-4)."""
        notes_text = RELEASE_NOTES.read_text(
            encoding="utf-8"
        ).lower()
        assert "is production-ready" not in notes_text, (
            "Release notes claim production-ready status"
        )
