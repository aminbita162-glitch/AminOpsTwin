"""Accessibility configuration and status indicators (P7, §35, G4.12).

Design requirements (§35): clear visual hierarchy, consistent
typography, keyboard operation, meaningful text labels, non-color-
only status indication and bounded animation.  No decorative
animation may obscure state or consume model tokens.

Status indicators use both colour and a text label/icon so that
colour-blind users and screen readers can distinguish states.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "StatusIndicator",
    "AccessibilityConfig",
]


class StatusIndicator(StrEnum):
    """Non-colour-only status indicator for dashboard states (§35).

    Each value carries a textual label so that status is never
    communicated by colour alone.  The CSS class and the label
    together convey the state.
    """

    PASS = "pass"
    FAIL = "fail"
    NOT_RUN = "not-run"
    UNKNOWN = "unknown"
    STALE = "stale"
    ACTIVE = "active"
    PENDING = "pending"
    DENIED = "denied"
    EXHAUSTED = "exhausted"
    RESERVED = "reserved"
    RECONCILING = "reconciling"
    COMPLETED = "completed"
    DEMO = "demo"

    @property
    def label(self) -> str:
        """Human-readable English label for this indicator."""
        labels: dict[str, str] = {
            "pass": "Pass",
            "fail": "Fail",
            "not-run": "Not Run",
            "unknown": "Unknown",
            "stale": "Stale",
            "active": "Active",
            "pending": "Pending",
            "denied": "Denied",
            "exhausted": "Exhausted",
            "reserved": "Reserved",
            "reconciling": "Reconciling",
            "completed": "Completed",
            "demo": "Synthetic Demo",
        }
        return labels.get(self.value, self.value)

    @property
    def icon(self) -> str:
        """Single-character icon (non-colour indicator)."""
        icons: dict[str, str] = {
            "pass": "\u2713",       # check mark
            "fail": "\u2717",       # ballot X
            "not-run": "\u2014",    # em dash
            "unknown": "?",
            "stale": "~",
            "active": "\u25CF",     # black circle
            "pending": "\u25CB",    # white circle
            "denied": "\u26D4",     # no entry
            "exhausted": "!",      # exclamation
            "reserved": "\u229A",   # circled ring
            "reconciling": "\u21BB",  # clockwise arrow
            "completed": "\u2714",  # heavy check mark
            "demo": "D",
        }
        return icons.get(self.value, "?")


@dataclass(frozen=True)
class AccessibilityConfig:
    """Accessibility target configuration (§35, §37).

    The accessibility target and viewport matrix must be validated
    before calling the interface accessible or cross-platform
    verified.  No untested platform is labeled verified (G4.12).
    """

    keyboard_operable: bool = True
    non_colour_only_status: bool = True
    text_labels: bool = True
    bounded_animation: bool = True
    aria_labels: bool = True
    high_contrast: bool = True
    screen_reader_tested: bool = False
    """screen_reader_tested is False until independently verified."""

    def to_dict(self) -> dict[str, bool]:
        return {
            "keyboard_operable": self.keyboard_operable,
            "non_colour_only_status": self.non_colour_only_status,
            "text_labels": self.text_labels,
            "bounded_animation": self.bounded_animation,
            "aria_labels": self.aria_labels,
            "high_contrast": self.high_contrast,
            "screen_reader_tested": self.screen_reader_tested,
        }
