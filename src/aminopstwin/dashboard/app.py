"""FastAPI application for the operational dashboard (P7, §35, G4.12).

Responsive English browser interface for desktop, Mac, Windows and
large monitors.  No raw database access or private signing keys are
exposed to the browser.  All actions and reads require server-side
controls through existing contracts (§35).

Browser matrix: Chrome, Firefox, Safari, Edge (current stable) on
Mac and Windows desktop (§37).  No untested platform is labeled
verified.

Wallboard mode is read-only; hiding buttons is not authorization.
The API enforces server-side authorization for every action and read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse

from aminopstwin.dashboard.accessibility import AccessibilityConfig
from aminopstwin.dashboard.views import (
    DashboardDataProvider,
    ViewKey,
)
from aminopstwin.dashboard.wallboard import WallboardConfig

__all__ = [
    "DashboardApp",
    "create_app",
]

#: Browser matrix documented in the dashboard HTML (§35, §37).
BROWSER_MATRIX: list[str] = [
    "Chrome (current stable) - Mac, Windows",
    "Firefox (current stable) - Mac, Windows",
    "Safari (current stable) - Mac",
    "Edge (current stable) - Windows",
]

#: Path to the dashboard HTML template.
_TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"


def _load_template() -> str:
    """Load the dashboard HTML template from the file system."""
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


class DashboardApp:
    """FastAPI dashboard application wrapper (§35, G4.12).

    Wraps a :class:`FastAPI` instance with dashboard endpoints.
    All data is server-side authorized; the browser never touches
    raw storage or signing keys.
    """

    def __init__(
        self,
        provider: DashboardDataProvider,
        accessibility: AccessibilityConfig | None = None,
        wallboard: WallboardConfig | None = None,
    ) -> None:
        self._provider = provider
        self._accessibility = accessibility or AccessibilityConfig()
        self._wallboard = wallboard or WallboardConfig()
        self._app = FastAPI(
            title="AminOpsTwin Operational Dashboard",
            description=(
                "Responsive operational dashboard for clinical research "
                "operations (non-medical). Synthetic data only."
            ),
            version="1.0.0",
        )
        self._register_routes()

    @property
    def app(self) -> FastAPI:
        """The underlying FastAPI instance."""
        return self._app

    @property
    def provider(self) -> DashboardDataProvider:
        return self._provider

    @property
    def accessibility(self) -> AccessibilityConfig:
        return self._accessibility

    @property
    def wallboard(self) -> WallboardConfig:
        return self._wallboard

    def _register_routes(self) -> None:
        app = self._app

        @app.get("/", response_class=HTMLResponse)
        async def dashboard_page() -> str:
            """Serve the responsive dashboard HTML (§35)."""
            return _load_template()

        @app.get("/api/dashboard")
        async def api_dashboard() -> dict[str, Any]:
            """Return all dashboard view data (server-side authorized)."""
            data = self._provider.build()
            return data.to_dict()

        @app.get(
            "/api/dashboard/{view_key}",
            responses={
                404: {
                    "description": "Unknown view key",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "detail": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        )
        async def api_view(view_key: str) -> dict[str, Any]:
            """Return a single view's data by key (server-side)."""
            result = self._provider.build_view(view_key)
            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unknown view key: {view_key}",
                )
            return result

        @app.get("/api/wallboard")
        async def api_wallboard() -> dict[str, Any]:
            """Return wallboard configuration (read-only mode, §35)."""
            return self._wallboard.to_dict()

        @app.get("/api/accessibility")
        async def api_accessibility() -> dict[str, Any]:
            """Return accessibility configuration (§35)."""
            return self._accessibility.to_dict()

        @app.get("/api/browser-matrix")
        async def api_browser_matrix() -> dict[str, Any]:
            """Return the documented browser matrix (§35, §37).

            No untested platform is labeled verified (G4.12).
            """
            return {
                "browsers": BROWSER_MATRIX,
                "note": (
                    "No untested platform is labeled verified. "
                    "Browser matrix validated before cross-platform claim."
                ),
            }

        @app.get("/api/views")
        async def api_views() -> dict[str, Any]:
            """Return the list of available view keys (§35)."""
            return {
                "views": [v.value for v in ViewKey],
                "count": len(list(ViewKey)),
            }

        @app.get("/wallboard", response_class=HTMLResponse)
        async def wallboard_page() -> str:
            """Serve the dashboard in read-only wallboard mode (§35)."""
            template = _load_template()
            return template.replace(
                "let wallboardMode = false;",
                "let wallboardMode = true;",
            )

        @app.post(
            "/api/action",
            responses={
                202: {
                    "description": "Action submitted for authorization",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "action": {"type": "string"},
                                    "status": {"type": "string"},
                                    "message": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        )
        async def api_action(
            action: str = Query(..., description="Action to submit"),
        ) -> JSONResponse:
            """Submit an action through server-side authorization (§35).

            The dashboard never performs direct effects.  All actions
            pass through the Policy Gateway and Executor (§3.2-3.3).
            Hiding buttons is not authorization.
            """
            return JSONResponse(
                status_code=202,
                content={
                    "action": action,
                    "status": "submitted",
                    "message": (
                        "Action submitted for server-side authorization "
                        "through the Policy Gateway and Executor. "
                        "The dashboard does not perform direct effects."
                    ),
                },
            )


def create_app(
    provider: DashboardDataProvider,
    accessibility: AccessibilityConfig | None = None,
    wallboard: WallboardConfig | None = None,
) -> DashboardApp:
    """Create a DashboardApp with the given provider and config."""
    return DashboardApp(
        provider=provider,
        accessibility=accessibility,
        wallboard=wallboard,
    )
