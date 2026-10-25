"""Read-only wallboard mode for the operational dashboard (P7, §35, G4.12).

Provide a read-only wallboard mode.  Hiding buttons is not
authorization: all actions and reads require server-side controls
through existing contracts (§35).  The wallboard exposes only
aggregate queue and capacity — no patient or staff names.

Wallboard example: aggregate queue and capacity only, no patient or
staff names (§35).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "WallboardMode",
    "WallboardConfig",
]


class WallboardMode(StrEnum):
    """Wallboard display mode (§35).

    READ_ONLY: no action buttons rendered; all reads still
    server-side authorized.  Hiding buttons is not authorization.
    FULL: interactive dashboard with action buttons (subject to
    server-side authorization).
    """

    READ_ONLY = "READ_ONLY"
    FULL = "FULL"


@dataclass(frozen=True)
class WallboardConfig:
    """Wallboard configuration (§35).

    The wallboard exposes only aggregate operational data — no
    patient or staff names, no individual records.
    """

    mode: WallboardMode = WallboardMode.READ_ONLY
    show_capacity: bool = True
    show_queues: bool = True
    show_scenarios: bool = True
    show_assurance: bool = True
    show_patient_data: bool = False  # always False — forbidden (§35, N-1)
    show_staff_names: bool = False   # always False — forbidden (§35)

    def __post_init__(self) -> None:
        if self.show_patient_data:
            raise ValueError(
                "show_patient_data is forbidden (§35, N-1) — "
                "the wallboard must never display patient data"
            )
        if self.show_staff_names:
            raise ValueError(
                "show_staff_names is forbidden (§35) — "
                "the wallboard must never display staff names"
            )

    def to_dict(self) -> dict[str, bool | str]:
        return {
            "mode": self.mode.value,
            "show_capacity": self.show_capacity,
            "show_queues": self.show_queues,
            "show_scenarios": self.show_scenarios,
            "show_assurance": self.show_assurance,
            "show_patient_data": self.show_patient_data,
            "show_staff_names": self.show_staff_names,
        }
