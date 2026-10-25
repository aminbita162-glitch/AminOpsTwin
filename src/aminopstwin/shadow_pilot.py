"""Shadow Pilot Report generator (P14, G14.1).

Produces a sample Shadow Pilot report using synthetic aggregate data that
satisfies Data Contract v1.  The report is a calibration-style comparison
of predicted vs actual aggregate metrics, stored as a deterministic JSON
file under ``test_home/P14/``.

The report is reproducible: given the same synthetic input data, the same
report hash is produced every time.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aminopstwin.ingestion.shadow_gateway import (
    ShadowGateway,
    ShadowIngestionResult,
)

__all__ = [
    "ShadowPilotReport",
    "generate_shadow_pilot_report",
    "SHADOW_PILOT_SYNTHETIC_DATA",
]

REPO_ROOT = Path(__file__).parent.parent.parent.parent


#: Synthetic weekly aggregate data satisfying Data Contract v1.
#: This is labelled SYNTHETIC — no real clinical trial data.
SHADOW_PILOT_SYNTHETIC_DATA: list[dict[str, Any]] = [
    {
        "week_start": "2026-01-01",
        "week_end": "2026-01-07",
        "metric_name": "enrollment",
        "site_count": 12,
        "enrollment_count": 50,
        "active_sites": 10,
        "predicted_value": 45,
        "actual_value": 48,
        "variance": 3,
        "n_observations": 12,
    },
    {
        "week_start": "2026-01-08",
        "week_end": "2026-01-14",
        "metric_name": "enrollment",
        "site_count": 14,
        "enrollment_count": 55,
        "active_sites": 12,
        "predicted_value": 50,
        "actual_value": 52,
        "variance": 2,
        "n_observations": 14,
    },
    {
        "week_start": "2026-01-15",
        "week_end": "2026-01-21",
        "metric_name": "enrollment",
        "site_count": 15,
        "enrollment_count": 60,
        "active_sites": 13,
        "predicted_value": 55,
        "actual_value": 58,
        "variance": 3,
        "n_observations": 15,
    },
    {
        "week_start": "2026-01-22",
        "week_end": "2026-01-28",
        "metric_name": "enrollment",
        "site_count": 16,
        "enrollment_count": 65,
        "active_sites": 14,
        "predicted_value": 60,
        "actual_value": 61,
        "variance": 1,
        "n_observations": 16,
    },
    {
        "week_start": "2026-01-29",
        "week_end": "2026-02-04",
        "metric_name": "enrollment",
        "site_count": 18,
        "enrollment_count": 70,
        "active_sites": 16,
        "predicted_value": 65,
        "actual_value": 67,
        "variance": 2,
        "n_observations": 18,
    },
    {
        "week_start": "2026-01-01",
        "week_end": "2026-01-07",
        "metric_name": "screen_failure",
        "site_count": 12,
        "enrollment_count": 50,
        "active_sites": 10,
        "predicted_value": 12,
        "actual_value": 14,
        "variance": 2,
        "n_observations": 12,
    },
    {
        "week_start": "2026-01-08",
        "week_end": "2026-01-14",
        "metric_name": "screen_failure",
        "site_count": 14,
        "enrollment_count": 55,
        "active_sites": 12,
        "predicted_value": 13,
        "actual_value": 13,
        "variance": 0,
        "n_observations": 14,
    },
    {
        "week_start": "2026-01-15",
        "week_end": "2026-01-21",
        "metric_name": "screen_failure",
        "site_count": 15,
        "enrollment_count": 60,
        "active_sites": 13,
        "predicted_value": 14,
        "actual_value": 16,
        "variance": 2,
        "n_observations": 15,
    },
]


class ShadowPilotReport(BaseModel):
    """A sample Shadow Pilot report (P14, G14.1)."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    report_id: str
    report_type: str = "shadow_pilot"
    data_label: str = "SYNTHETIC"
    synthetic_notice: str = (
        "This Shadow Pilot report uses synthetic aggregate data. "
        "No real clinical trial data is included."
    )
    generated_at: str
    data_contract_version: str = "v1"
    k_min: int
    total_rows: int
    calibration: dict[str, Any] = Field(default_factory=dict)
    metrics_summary: dict[str, Any] = Field(default_factory=dict)
    ingestion_receipt_id: str
    report_hash: str


def _compute_report_hash(report_data: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash over the report data."""
    canonical = json.dumps(
        report_data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def generate_shadow_pilot_report(
    data: list[dict[str, Any]] | None = None,
    k_min: int = 5,
) -> ShadowPilotReport:
    """Generate a Shadow Pilot report from synthetic aggregate data.

    The report is deterministic: the same input data produces the same
    report hash every time.
    """
    if data is None:
        data = SHADOW_PILOT_SYNTHETIC_DATA

    gw = ShadowGateway(k_min=k_min)
    json_content = json.dumps(data, ensure_ascii=False)
    result: ShadowIngestionResult = gw.ingest_json(json_content)

    if not result.admitted:
        raise RuntimeError(
            f"shadow pilot data failed ingestion: {result.status} "
            f"({result.reason_code})"
        )

    assert result.receipt is not None

    # Use a deterministic receipt_id (derived from input hash only)
    # so the report hash is fully reproducible.
    deterministic_receipt_id = hashlib.sha256(
        json_content.encode("utf-8")
    ).hexdigest()[:16]

    # Build calibration comparison from the receipt's forecast_vs_actual
    fvsa = result.receipt.forecast_vs_actual
    comparisons = fvsa.get("comparisons", [])

    # Group by metric_name for summary
    by_metric: dict[str, list[dict[str, Any]]] = {}
    for comp in comparisons:
        metric = comp.get("metric_name", "unknown")
        if metric not in by_metric:
            by_metric[metric] = []
        by_metric[metric].append(comp)

    metrics_summary: dict[str, Any] = {}
    for metric, comps in by_metric.items():
        predicted_values = [c["predicted"] for c in comps]
        actual_values = [c["actual"] for c in comps]
        diffs = [c["difference"] for c in comps]
        total_predicted = sum(predicted_values)
        total_actual = sum(actual_values)
        total_diff = sum(diffs)
        mean_diff = total_diff / len(diffs) if diffs else 0
        mape = (
            sum(abs(d / p) for d, p in zip(diffs, predicted_values, strict=False))
            / len(diffs)
            * 100
        ) if diffs and all(p != 0 for p in predicted_values) else 0
        metrics_summary[metric] = {
            "weeks": len(comps),
            "total_predicted": total_predicted,
            "total_actual": total_actual,
            "mean_difference": round(mean_diff, 4),
            "total_difference": total_diff,
            "mape_pct": round(mape, 4),
        }

    # Deterministic generated_at (fixed timestamp for reproducibility)
    generated_at = "2026-10-25T00:00:00Z"

    report_data: dict[str, Any] = {
        "report_id": hashlib.sha256(
            json_content.encode("utf-8")
        ).hexdigest()[:16],
        "report_type": "shadow_pilot",
        "data_label": "SYNTHETIC",
        "synthetic_notice": (
            "This Shadow Pilot report uses synthetic aggregate data. "
            "No real clinical trial data is included."
        ),
        "generated_at": generated_at,
        "data_contract_version": "v1",
        "k_min": k_min,
        "total_rows": len(data),
        "calibration": {
            "comparisons": comparisons,
            "count": len(comparisons),
        },
        "metrics_summary": metrics_summary,
        "ingestion_receipt_id": deterministic_receipt_id,
    }

    report_hash = _compute_report_hash(report_data)
    report_data["report_hash"] = report_hash

    return ShadowPilotReport(**report_data)


def save_shadow_pilot_report(
    report: ShadowPilotReport,
    output_path: Path,
) -> Path:
    """Save a Shadow Pilot report to a JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_json = json.dumps(
        report.model_dump(),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    output_path.write_text(report_json + "\n", encoding="utf-8")
    return output_path
