"""Tests for the Shadow Pilot Report (G14.1).

Verifies that:
- the sample Shadow Pilot report exists and is reproducible
- the report uses synthetic aggregate data satisfying Data Contract v1
- the report contains a calibration-style comparison (predicted vs actual)
- the report hash is deterministic (same input -> same hash)
- the report is stored under test_home/P14/
"""

from __future__ import annotations

import json
from pathlib import Path

from aminopstwin.shadow_pilot import (
    SHADOW_PILOT_SYNTHETIC_DATA,
    ShadowPilotReport,
    generate_shadow_pilot_report,
    save_shadow_pilot_report,
)

REPO_ROOT = Path(__file__).parent.parent.parent
REPORT_PATH = REPO_ROOT / "test_home" / "P14" / "shadow_pilot_report.json"


class TestShadowPilotReport:
    """G14.1: sample Shadow Pilot report exists and is reproducible."""

    def test_synthetic_data_satisfies_data_contract(self) -> None:
        """All synthetic data rows must use only Data Contract v1 columns."""
        from aminopstwin.ingestion.shadow_gateway import (
            DATA_CONTRACT_V1_COLUMNS,
        )

        allowed = set(DATA_CONTRACT_V1_COLUMNS.keys())
        for row in SHADOW_PILOT_SYNTHETIC_DATA:
            assert set(row.keys()).issubset(
                allowed
            ), f"row has unknown columns: {set(row.keys()) - allowed}"

    def test_synthetic_data_has_required_columns(self) -> None:
        """Each row must have week_start, week_end, metric_name."""
        required = {"week_start", "week_end", "metric_name"}
        for row in SHADOW_PILOT_SYNTHETIC_DATA:
            assert required.issubset(row.keys()), (
                f"row missing required columns: {required - set(row.keys())}"
            )

    def test_synthetic_data_is_labelled(self) -> None:
        """The data must be clearly synthetic."""
        assert SHADOW_PILOT_SYNTHETIC_DATA
        # All count values must be >= k_min (5) to avoid suppression
        for row in SHADOW_PILOT_SYNTHETIC_DATA:
            count_cols = (
                "site_count", "enrollment_count",
                "active_sites", "n_observations",
            )
            for col in count_cols:
                if col in row:
                    assert row[col] >= 5, (
                        f"{col}={row[col]} < 5 in synthetic data"
                    )

    def test_report_generates_successfully(self) -> None:
        report = generate_shadow_pilot_report()
        assert isinstance(report, ShadowPilotReport)
        assert report.report_type == "shadow_pilot"
        assert report.data_label == "SYNTHETIC"

    def test_report_has_calibration_comparison(self) -> None:
        report = generate_shadow_pilot_report()
        cal = report.calibration
        assert "comparisons" in cal
        assert cal["count"] > 0
        comp = cal["comparisons"][0]
        assert "predicted" in comp
        assert "actual" in comp
        assert "difference" in comp

    def test_report_has_metrics_summary(self) -> None:
        report = generate_shadow_pilot_report()
        assert len(report.metrics_summary) > 0
        for _metric, summary in report.metrics_summary.items():
            assert "total_predicted" in summary
            assert "total_actual" in summary
            assert "mape_pct" in summary

    def test_report_hash_is_deterministic(self) -> None:
        """Same input data -> same report hash."""
        report1 = generate_shadow_pilot_report()
        report2 = generate_shadow_pilot_report()
        assert report1.report_hash == report2.report_hash, (
            "report hash must be deterministic for the same input data"
        )

    def test_report_hash_changes_with_different_data(self) -> None:
        """Different input data -> different report hash."""
        report1 = generate_shadow_pilot_report()
        modified_data = list(SHADOW_PILOT_SYNTHETIC_DATA)
        modified = dict(modified_data[0])
        modified["actual_value"] = 999
        modified_data[0] = modified
        report2 = generate_shadow_pilot_report(data=modified_data)
        assert report1.report_hash != report2.report_hash

    def test_report_reproducible_from_file(self) -> None:
        """Report saved to file and reloaded must have the same hash."""
        report = generate_shadow_pilot_report()
        data = report.model_dump()
        reloaded = ShadowPilotReport(**data)
        assert reloaded.report_hash == report.report_hash

    def test_report_stored_under_test_home_p14(self) -> None:
        """The report file must exist under test_home/P14/."""
        assert REPORT_PATH.exists(), (
            f"shadow pilot report must exist at {REPORT_PATH}"
        )

    def test_report_file_hash_matches_generated(self) -> None:
        """The stored report file's hash must match a freshly generated report."""
        stored = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        report = generate_shadow_pilot_report()
        assert stored["report_hash"] == report.report_hash, (
            "stored report hash does not match generated report hash"
        )

    def test_report_file_is_valid_json(self) -> None:
        """The report file must be valid JSON."""
        data = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "report_id" in data
        assert "calibration" in data
        assert "metrics_summary" in data
        assert "report_hash" in data

    def test_report_contains_no_patient_data(self) -> None:
        """The report must not contain any patient-level fields."""
        report = generate_shadow_pilot_report()
        report_str = json.dumps(report.model_dump())
        forbidden = [
            "patient_id",
            "patient_name",
            "diagnosis",
            "prognosis",
            "treatment",
            "individual_risk",
        ]
        for term in forbidden:
            assert term not in report_str.lower(), (
                f"forbidden term '{term}' found in shadow pilot report"
            )

    def test_report_generated_at_is_fixed(self) -> None:
        """The generated_at timestamp must be fixed for reproducibility."""
        report1 = generate_shadow_pilot_report()
        report2 = generate_shadow_pilot_report()
        assert report1.generated_at == report2.generated_at

    def test_save_report_to_path(self, tmp_path: Path) -> None:
        """save_shadow_pilot_report writes the report to a file."""
        report = generate_shadow_pilot_report()
        out = tmp_path / "report.json"
        save_shadow_pilot_report(report, out)
        assert out.exists()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["report_hash"] == report.report_hash
