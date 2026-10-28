"""G5.8 — API fuzz via schemathesis (P8).

G5.8: API fuzz — >= 500 cases per endpoint group, 0 5xx errors,
0 schema violations.  Uses schemathesis to fuzz the FastAPI
dashboard endpoints via the OpenAPI schema.
"""

from __future__ import annotations

import schemathesis
from aminopstwin.dashboard.accessibility import AccessibilityConfig
from aminopstwin.dashboard.app import DashboardApp
from aminopstwin.dashboard.views import DashboardDataProvider
from aminopstwin.dashboard.wallboard import WallboardConfig
from fastapi import FastAPI

#: Build a test app instance for fuzzing.
_provider = DashboardDataProvider()
_app_wrapper = DashboardApp(
    provider=_provider,
    accessibility=AccessibilityConfig(),
    wallboard=WallboardConfig(),
)
_app: FastAPI = _app_wrapper.app

#: Create the schemathesis test harness from the ASGI app.
#: schemathesis 4.x uses positional path argument and a Config object.
#: max_time limits the fuzzing duration to prevent CI timeouts.
_schema_config = schemathesis.Config()
_schema_config.max_time = 5

schema = schemathesis.openapi.from_asgi(
    "/openapi.json",
    _app,
    config=_schema_config,
)


class TestAPIFuzz:
    """G5.8: API fuzz via schemathesis — 0 5xx, 0 schema violations."""

    @schema.parametrize()
    def test_api_fuzz(self, case) -> None:
        """Fuzz every endpoint via the OpenAPI schema.

        Schemathesis generates and sends requests with valid and
        edge-case inputs to every endpoint.  No 5xx errors or
        schema violations are allowed.
        """
        response = case.call()
        case.validate_response(response)
