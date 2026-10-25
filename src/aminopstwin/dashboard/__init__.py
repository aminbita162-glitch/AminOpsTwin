"""Responsive operational dashboard and user interface (P7, §35, G4.12).

English responsive browser interface for desktop, Mac, Windows and
large monitors.  Seven required views, read-only wallboard mode,
accessibility baseline, and server-side authorization for all
actions and reads.

Browser matrix: Chrome, Firefox, Safari, Edge (current stable) on
Mac and Windows desktop (§37 confirmed owner defaults).  No
untested platform is labeled verified.

No raw database access or private signing keys are exposed to the
browser.  Hiding buttons is not authorization: all actions and
reads require server-side controls through existing contracts (§35).
"""

from aminopstwin.dashboard.accessibility import AccessibilityConfig, StatusIndicator
from aminopstwin.dashboard.app import DashboardApp, create_app
from aminopstwin.dashboard.views import DashboardData, DashboardDataProvider
from aminopstwin.dashboard.wallboard import WallboardConfig, WallboardMode

__all__ = [
    "DashboardData",
    "DashboardDataProvider",
    "create_app",
    "DashboardApp",
    "WallboardConfig",
    "WallboardMode",
    "StatusIndicator",
    "AccessibilityConfig",
]
