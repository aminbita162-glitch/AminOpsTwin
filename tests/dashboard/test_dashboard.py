"""G4.12 — Dashboard correctness tests (P7, §35).

All declared UI acceptance flows pass on the approved
browser/viewport matrix; all attempted unauthorized UI/API actions
deny; stale/UNKNOWN/demo indicators match authoritative state.
No untested platform is labeled verified (G4.12).

Required views (§35):
    - Overview: synthetic/demo status, resource capacity, queues
    - Scenario comparison: baseline, deltas, assumptions, uncertainty
    - Evidence: source versions, rights status, claim-to-source paths
    - Workflow: current state, UNKNOWN/reconciliation, receipts
    - Budget: remaining/reserved/actual counters, fallback status
    - Assurance: latest attempt, last success, failures, stale status
    - Experience: candidate versus active, promotion evidence

Wallboard mode: read-only, no patient or staff names (§35).
Accessibility: keyboard operable, non-colour-only status, meaningful
labels, bounded animation (§35).
"""

from __future__ import annotations

import datetime as _dt

import pytest
from aminopstwin.dashboard.accessibility import (
    AccessibilityConfig,
    StatusIndicator,
)
from aminopstwin.dashboard.app import BROWSER_MATRIX, DashboardApp
from aminopstwin.dashboard.views import (
    DashboardData,
    DashboardDataProvider,
    ViewKey,
)
from aminopstwin.dashboard.wallboard import WallboardConfig, WallboardMode
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider() -> DashboardDataProvider:
    """Build a minimal provider with no subsystems (default data)."""
    return DashboardDataProvider()


def _make_app(
    provider: DashboardDataProvider | None = None,
    wallboard: WallboardConfig | None = None,
) -> DashboardApp:
    """Build a DashboardApp for testing."""
    return DashboardApp(
        provider=provider or _make_provider(),
        wallboard=wallboard or WallboardConfig(),
    )


# ---------------------------------------------------------------------------
# View key tests — seven required views (§35)
# ---------------------------------------------------------------------------


class TestSevenRequiredViews:
    """G4.12: all seven required views are present and accessible."""

    def test_view_count_is_seven(self) -> None:
        views = list(ViewKey)
        assert len(views) == 7, "§35 requires exactly seven views"

    def test_view_keys_match_directive(self) -> None:
        expected = {
            "overview",
            "scenario_comparison",
            "evidence",
            "workflow",
            "budget",
            "assurance",
            "experience",
        }
        actual = {v.value for v in ViewKey}
        assert actual == expected

    def test_dashboard_data_has_all_views(self) -> None:
        data = DashboardData()
        d = data.to_dict()
        for key in ViewKey:
            assert key.value in d, f"missing view: {key}"

    def test_view_by_key_returns_data(self) -> None:
        data = DashboardData()
        for key in ViewKey:
            result = data.view_by_key(key.value)
            assert result is not None, f"view returned None: {key}"

    def test_view_by_unknown_key_returns_none(self) -> None:
        data = DashboardData()
        assert data.view_by_key("nonexistent") is None


# ---------------------------------------------------------------------------
# Overview view — synthetic/demo status (§35)
# ---------------------------------------------------------------------------


class TestOverviewView:
    """Overview: synthetic/demo status, resource capacity, queues."""

    def test_demo_status_is_synthetic(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert "synthetic" in data.overview.demo_status.lower()
        assert data.overview.is_synthetic is True

    def test_demo_status_text_matches_directive(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.overview.demo_status == (
            "Synthetic scenario - not live organizational data"
        )

    def test_overview_has_scenario_count(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert isinstance(data.overview.scenario_count, int)


# ---------------------------------------------------------------------------
# Scenario comparison view (§35)
# ---------------------------------------------------------------------------


class TestScenarioComparisonView:
    """Scenario comparison: baseline, deltas, uncertainty."""

    def test_default_has_no_comparisons(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.scenario_comparison.delta_count == 0
        assert len(data.scenario_comparison.comparisons) == 0

    def test_not_estimable_reason_is_none_by_default(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.scenario_comparison.not_estimable_reason is None


# ---------------------------------------------------------------------------
# Evidence view (§35)
# ---------------------------------------------------------------------------


class TestEvidenceView:
    """Evidence: source versions, rights status."""

    def test_default_evidence_is_empty(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.evidence.approved_count == 0
        assert data.evidence.active_count == 0


# ---------------------------------------------------------------------------
# Workflow view — UNKNOWN/reconciliation (§35)
# ---------------------------------------------------------------------------


class TestWorkflowView:
    """Workflow: current state, UNKNOWN/reconciliation, receipts."""

    def test_default_workflow_is_pending(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.workflow.current_state == "PENDING"
        assert data.workflow.state_indicator == StatusIndicator.PENDING

    def test_unknown_count_is_zero_by_default(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.workflow.unknown_count == 0

    def test_reconciling_count_is_zero_by_default(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.workflow.reconciling_count == 0


# ---------------------------------------------------------------------------
# Budget view — remaining/reserved/actual, fallback (§35)
# ---------------------------------------------------------------------------


class TestBudgetView:
    """Budget: remaining/reserved/actual counters, fallback status."""

    def test_default_budget_is_zero(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.budget.session_remaining == 0
        assert data.budget.workflow_remaining == 0
        assert data.budget.capability_remaining == 0

    def test_fallback_not_active_by_default(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.budget.fallback_active is False
        assert data.budget.fallback_reason is None

    def test_budget_with_governor(self) -> None:
        from aminopstwin.tokens.budget import BudgetGovernor
        governor = BudgetGovernor(
            session_budget=1000,
            workflow_budget=500,
            capability_budget=200,
        )
        provider = DashboardDataProvider(budget_governor=governor)
        data = provider.build()
        assert data.budget.session_remaining == 1000
        assert data.budget.workflow_remaining == 500
        assert data.budget.capability_remaining == 200
        assert data.budget.indicator == StatusIndicator.ACTIVE
        assert data.budget.fallback_active is False

    def test_budget_exhausted_shows_fallback(self) -> None:
        from aminopstwin.tokens.budget import BudgetGovernor, BudgetLevel
        governor = BudgetGovernor(
            session_budget=10,
            workflow_budget=10,
            capability_budget=10,
        )
        # Exhaust the session budget
        governor.reserve(BudgetLevel.SESSION, 10)
        provider = DashboardDataProvider(budget_governor=governor)
        data = provider.build()
        assert data.budget.fallback_active is True
        assert data.budget.fallback_reason == "BUDGET_SESSION_EXHAUSTED"
        assert data.budget.indicator == StatusIndicator.EXHAUSTED


# ---------------------------------------------------------------------------
# Assurance view — latest attempt, last success, stale (§35)
# ---------------------------------------------------------------------------


class TestAssuranceView:
    """Assurance: latest attempt, last success, failures, stale."""

    def test_default_assurance_is_not_run(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.assurance.indicator == StatusIndicator.NOT_RUN
        assert data.assurance.latest_attempt_id is None
        assert data.assurance.last_success_id is None

    def test_assurance_with_runner_and_scheduler(self) -> None:
        from aminopstwin.assurance.runner import AssuranceRunner
        from aminopstwin.assurance.scheduler import (
            MissedRunPolicy,
            ScheduleConfig,
            WeeklyScheduler,
        )
        from aminopstwin.contracts.clock import SeededClock

        clock = SeededClock(
            _dt.datetime(2026, 1, 5, 9, 0, 0, tzinfo=_dt.UTC)
        )
        config = ScheduleConfig(
            deployment_id="dep-test",
            tenant_scope="tenant-test",
            suite_version="1.0.0",
            day_of_week=0,
            hour=9,
            minute=0,
            timezone="UTC",
            missed_run_policy=MissedRunPolicy.SKIP,
            retention_weeks=30,
        )
        scheduler = WeeklyScheduler(config, clock)
        runner = AssuranceRunner(config, clock)

        provider = DashboardDataProvider(
            assurance_runner=runner,
            scheduler=scheduler,
        )
        data = provider.build()
        # Before any run, assurance is NOT_RUN
        assert data.assurance.indicator == StatusIndicator.NOT_RUN


# ---------------------------------------------------------------------------
# Experience view (§35)
# ---------------------------------------------------------------------------


class TestExperienceView:
    """Experience: candidate versus active, promotion evidence."""

    def test_default_experience_is_empty(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert data.experience.active_count == 0
        assert data.experience.candidate_count == 0
        assert data.experience.promoted_count == 0

    def test_experience_with_store(self) -> None:
        from aminopstwin.executor.experience import ExperienceStore
        store = ExperienceStore()
        store.observe(
            experience_id="exp-001",
            task_category="capacity",
            input_hash="a" * 64,
            policy_epoch=0,
            selected_method="deterministic",
            test_outcome="pass",
        )
        provider = DashboardDataProvider(experience_store=store)
        data = provider.build()
        assert data.experience.active_count == 0
        assert data.experience.candidate_count == 0
        assert len(data.experience.records) == 1


# ---------------------------------------------------------------------------
# Wallboard mode (§35)
# ---------------------------------------------------------------------------


class TestWallboardMode:
    """Read-only wallboard mode; no patient or staff names."""

    def test_wallboard_config_defaults_to_read_only(self) -> None:
        wb = WallboardConfig()
        assert wb.mode == WallboardMode.READ_ONLY

    def test_wallboard_config_shows_capacity(self) -> None:
        wb = WallboardConfig()
        assert wb.show_capacity is True

    def test_wallboard_config_shows_queues(self) -> None:
        wb = WallboardConfig()
        assert wb.show_queues is True

    def test_wallboard_config_does_not_show_patient_data(self) -> None:
        wb = WallboardConfig()
        assert wb.show_patient_data is False

    def test_wallboard_config_does_not_show_staff_names(self) -> None:
        wb = WallboardConfig()
        assert wb.show_staff_names is False

    def test_wallboard_forbidden_patient_data_raises(self) -> None:
        with pytest.raises(
            ValueError, match="show_patient_data.*forbidden"
        ):
            WallboardConfig(show_patient_data=True)

    def test_wallboard_forbidden_staff_names_raises(self) -> None:
        with pytest.raises(
            ValueError, match="show_staff_names.*forbidden"
        ):
            WallboardConfig(show_staff_names=True)

    def test_wallboard_full_mode_allowed(self) -> None:
        wb = WallboardConfig(mode=WallboardMode.FULL)
        assert wb.mode == WallboardMode.FULL
        assert wb.show_patient_data is False  # still forbidden


# ---------------------------------------------------------------------------
# Accessibility (§35)
# ---------------------------------------------------------------------------


class TestAccessibility:
    """Accessibility: keyboard, non-colour-only, labels, animation."""

    def test_accessibility_defaults(self) -> None:
        acc = AccessibilityConfig()
        assert acc.keyboard_operable is True
        assert acc.non_colour_only_status is True
        assert acc.text_labels is True
        assert acc.bounded_animation is True
        assert acc.aria_labels is True
        assert acc.high_contrast is True

    def test_screen_reader_not_tested_by_default(self) -> None:
        acc = AccessibilityConfig()
        assert acc.screen_reader_tested is False

    def test_status_indicator_has_label_and_icon(self) -> None:
        for indicator in StatusIndicator:
            assert indicator.label, f"no label for {indicator}"
            assert indicator.icon, f"no icon for {indicator}"

    def test_status_indicators_are_distinct(self) -> None:
        labels = {ind.label for ind in StatusIndicator}
        # All labels should be unique
        assert len(labels) == len(list(StatusIndicator))

    def test_status_indicator_pass(self) -> None:
        assert StatusIndicator.PASS.label == "Pass"
        assert StatusIndicator.PASS.icon == "\u2713"

    def test_status_indicator_fail(self) -> None:
        assert StatusIndicator.FAIL.label == "Fail"
        assert StatusIndicator.FAIL.icon == "\u2717"

    def test_status_indicator_unknown(self) -> None:
        assert StatusIndicator.UNKNOWN.label == "Unknown"
        assert StatusIndicator.UNKNOWN.icon == "?"

    def test_status_indicator_not_run(self) -> None:
        assert StatusIndicator.NOT_RUN.label == "Not Run"
        assert StatusIndicator.NOT_RUN.icon == "\u2014"


# ---------------------------------------------------------------------------
# Browser matrix (§35, §37, G4.12)
# ---------------------------------------------------------------------------


class TestBrowserMatrix:
    """No untested platform is labeled verified (G4.12)."""

    def test_browser_matrix_has_four_browsers(self) -> None:
        assert len(BROWSER_MATRIX) == 4

    def test_browser_matrix_includes_chrome(self) -> None:
        assert any("Chrome" in b for b in BROWSER_MATRIX)

    def test_browser_matrix_includes_firefox(self) -> None:
        assert any("Firefox" in b for b in BROWSER_MATRIX)

    def test_browser_matrix_includes_safari(self) -> None:
        assert any("Safari" in b for b in BROWSER_MATRIX)

    def test_browser_matrix_includes_edge(self) -> None:
        assert any("Edge" in b for b in BROWSER_MATRIX)

    def test_browser_matrix_includes_mac(self) -> None:
        assert any("Mac" in b for b in BROWSER_MATRIX)

    def test_browser_matrix_includes_windows(self) -> None:
        assert any("Windows" in b for b in BROWSER_MATRIX)


# ---------------------------------------------------------------------------
# FastAPI endpoint tests (§35)
# ---------------------------------------------------------------------------


class TestDashboardAPI:
    """API endpoints serve dashboard data server-side (§35)."""

    def test_get_dashboard_page(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get(
            "content-type", ""
        )
        assert "AminOpsTwin" in resp.text

    def test_get_api_dashboard(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "overview" in data
        assert "scenario_comparison" in data
        assert "evidence" in data
        assert "workflow" in data
        assert "budget" in data
        assert "assurance" in data
        assert "experience" in data
        assert "wallboard" in data
        assert "view_keys" in data

    def test_get_api_view_overview(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/api/dashboard/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "demo_status" in data
        assert "is_synthetic" in data
        assert data["is_synthetic"] is True

    def test_get_api_view_unknown_returns_404(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/api/dashboard/nonexistent")
        assert resp.status_code == 404

    def test_get_api_wallboard(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/api/wallboard")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "READ_ONLY"
        assert data["show_patient_data"] is False
        assert data["show_staff_names"] is False

    def test_get_api_accessibility(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/api/accessibility")
        assert resp.status_code == 200
        data = resp.json()
        assert data["keyboard_operable"] is True
        assert data["non_colour_only_status"] is True

    def test_get_api_browser_matrix(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/api/browser-matrix")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["browsers"]) == 4
        assert "No untested platform is labeled verified" in data["note"]

    def test_get_api_views(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/api/views")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 7
        assert "overview" in data["views"]

    def test_get_wallboard_page(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/wallboard")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get(
            "content-type", ""
        )

    def test_post_action_returns_accepted(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.post("/api/action?action=test")
        assert resp.status_code == 202
        data = resp.json()
        assert data["status"] == "submitted"
        assert "processing" in data["message"]

    def test_action_does_not_perform_direct_effects(self) -> None:
        """The dashboard does not perform direct effects (§35)."""
        app = _make_app()
        client = TestClient(app.app)
        resp = client.post("/api/action?action=run_scenario")
        data = resp.json()
        assert "does not perform direct effects" in data["message"]


# ---------------------------------------------------------------------------
# Stale/UNKNOWN/demo state display (§35)
# ---------------------------------------------------------------------------


class TestStaleStateDisplay:
    """Display stale, incomplete, unknown, failed, not-run distinctly."""

    def test_not_run_is_distinct_from_pass_and_fail(self) -> None:
        assert StatusIndicator.NOT_RUN != StatusIndicator.PASS
        assert StatusIndicator.NOT_RUN != StatusIndicator.FAIL
        assert StatusIndicator.NOT_RUN.label == "Not Run"

    def test_unknown_is_distinct_from_pass_and_fail(self) -> None:
        assert StatusIndicator.UNKNOWN != StatusIndicator.PASS
        assert StatusIndicator.UNKNOWN != StatusIndicator.FAIL
        assert StatusIndicator.UNKNOWN.label == "Unknown"

    def test_stale_is_distinct(self) -> None:
        assert StatusIndicator.STALE.label == "Stale"
        assert StatusIndicator.STALE != StatusIndicator.ACTIVE

    def test_demo_is_distinct(self) -> None:
        assert StatusIndicator.DEMO.label == "Synthetic Demo"
        assert StatusIndicator.DEMO != StatusIndicator.ACTIVE

    def test_failed_is_distinct(self) -> None:
        assert StatusIndicator.FAIL.label == "Fail"
        assert StatusIndicator.FAIL != StatusIndicator.PASS

    def test_all_status_indicators_have_unique_icons(self) -> None:
        icons = [ind.icon for ind in StatusIndicator]
        # Icons should be unique (non-colour-only indication)
        assert len(set(icons)) == len(icons)


# ---------------------------------------------------------------------------
# Dashboard data serialisation (§35)
# ---------------------------------------------------------------------------


class TestDashboardDataSerialisation:
    """Dashboard data is JSON-serialisable for API responses."""

    def test_to_dict_is_json_serialisable(self) -> None:
        import json
        data = DashboardData()
        d = data.to_dict()
        # Should not raise
        json.dumps(d)

    def test_to_dict_has_wallboard_config(self) -> None:
        data = DashboardData()
        d = data.to_dict()
        assert "wallboard" in d
        assert d["wallboard"]["show_patient_data"] is False

    def test_to_dict_has_view_keys(self) -> None:
        data = DashboardData()
        d = data.to_dict()
        assert "view_keys" in d
        assert len(d["view_keys"]) == 7


# ---------------------------------------------------------------------------
# No raw database access or signing keys exposed (§35)
# ---------------------------------------------------------------------------


class TestNoRawAccess:
    """No raw database access or private signing keys to the browser."""

    def test_dashboard_data_has_no_secrets(self) -> None:
        provider = _make_provider()
        data = provider.build()
        d = data.to_dict()
        # No secret-like keys should appear
        json_str = str(d)
        for forbidden in [
            "password",
            "secret",
            "private_key",
            "signing_key",
            "api_key",
        ]:
            assert forbidden not in json_str.lower(), (
                f"forbidden key '{forbidden}' in dashboard data"
            )

    def test_dashboard_data_has_no_db_connection(self) -> None:
        provider = _make_provider()
        data = provider.build()
        d = data.to_dict()
        json_str = str(d)
        for forbidden in [
            "connection_string",
            "dsn",
            "database_url",
            "postgres://",
            "sqlite://",
        ]:
            assert forbidden not in json_str.lower(), (
                f"forbidden db reference '{forbidden}' in dashboard data"
            )

    def test_api_dashboard_has_no_secrets(self) -> None:
        app = _make_app()
        client = TestClient(app.app)
        resp = client.get("/api/dashboard")
        data = resp.json()
        json_str = str(data)
        for forbidden in [
            "password",
            "secret",
            "private_key",
            "signing_key",
        ]:
            assert forbidden not in json_str.lower()


# ---------------------------------------------------------------------------
# Non-clinical boundary (§35, §2.2)
# ---------------------------------------------------------------------------


class TestNonClinicalBoundary:
    """The dashboard must not display clinical/patient data (§35, §2.2)."""

    def test_no_patient_data_in_overview(self) -> None:
        provider = _make_provider()
        data = provider.build()
        d = data.overview.to_dict()
        json_str = str(d)
        for term in ["patient", "diagnosis", "treatment", "dose"]:
            assert term not in json_str.lower()

    def test_no_staff_names_in_wallboard(self) -> None:
        wb = WallboardConfig()
        d = wb.to_dict()
        assert d["show_staff_names"] is False
        assert d["show_patient_data"] is False

    def test_demo_status_says_synthetic(self) -> None:
        provider = _make_provider()
        data = provider.build()
        assert "synthetic" in data.overview.demo_status.lower()
        assert "not live" in data.overview.demo_status.lower()
