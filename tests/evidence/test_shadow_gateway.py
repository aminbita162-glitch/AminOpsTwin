"""Tests for the Shadow Ingestion Gateway (G13.4).

Verifies that:
- valid aggregate CSV/JSON is admitted
- unknown columns are rejected
- missing required columns are rejected
- k-min cell suppression is applied (default k=5)
- non-aggregate data (patient-level fields) is rejected
- empty content is rejected
- hashed receipts are produced
- forecast-vs-actual comparison is output (no free-text interpretation)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aminopstwin.ingestion.shadow_gateway import (
    DATA_CONTRACT_V1_COLUMNS,
    DEFAULT_K_MIN,
    ShadowGateway,
    ShadowIngestionError,
    ShadowIngestionStatus,
)

REPO_ROOT = Path(__file__).parent.parent.parent


class TestShadowGatewayCSV:
    """G13.4: Shadow ingestion with CSV input."""

    def test_valid_csv_admitted(self, tmp_path: Path) -> None:
        csv_content = (
            "week_start,week_end,metric_name,site_count,enrollment_count,"
            "predicted_value,actual_value\n"
            "2026-01-01,2026-01-07,enrollment,10,50,45,48\n"
            "2026-01-08,2026-01-14,enrollment,12,55,50,52\n"
        )
        gw = ShadowGateway(receipts_dir=tmp_path / "receipts")
        result = gw.ingest_csv(csv_content)
        assert result.admitted
        assert result.receipt is not None
        assert result.receipt.status == ShadowIngestionStatus.ADMITTED
        assert result.receipt.row_count == 2

    def test_unknown_columns_rejected(self) -> None:
        csv_content = (
            "week_start,week_end,metric_name,evil_column\n"
            "2026-01-01,2026-01-07,enrollment,999\n"
        )
        gw = ShadowGateway()
        result = gw.ingest_csv(csv_content)
        assert result.status == ShadowIngestionStatus.REJECTED_UNKNOWN_COLUMNS
        assert result.reason_code == "GW-SCHEMA-006"

    def test_missing_required_rejected(self) -> None:
        csv_content = (
            "metric_name,site_count\n"
            "enrollment,10\n"
        )
        gw = ShadowGateway()
        result = gw.ingest_csv(csv_content)
        assert result.status == ShadowIngestionStatus.REJECTED_MISSING_REQUIRED

    def test_empty_csv_rejected(self) -> None:
        gw = ShadowGateway()
        result = gw.ingest_csv("")
        assert result.status == ShadowIngestionStatus.REJECTED_EMPTY

    def test_empty_json_rejected(self) -> None:
        gw = ShadowGateway()
        result = gw.ingest_json("[]")
        assert result.status == ShadowIngestionStatus.REJECTED_EMPTY

    def test_k_min_suppression_applied(self) -> None:
        """Count columns with values < k_min (5) are suppressed."""
        csv_content = (
            "week_start,week_end,metric_name,site_count,enrollment_count\n"
            "2026-01-01,2026-01-07,enrollment,3,50\n"
            "2026-01-08,2026-01-14,enrollment,10,55\n"
        )
        gw = ShadowGateway(k_min=5)
        result = gw.ingest_csv(csv_content)
        assert result.admitted
        assert result.receipt is not None
        assert result.receipt.suppressed_cells >= 1
        # The first row's site_count (3 < 5) should be suppressed
        assert result.rows[0]["site_count"] is None
        # The second row's site_count (10 >= 5) should not be suppressed
        assert result.rows[1]["site_count"] == 10

    def test_k_min_custom_threshold(self) -> None:
        """With k_min=10, more cells should be suppressed."""
        csv_content = (
            "week_start,week_end,metric_name,site_count,enrollment_count\n"
            "2026-01-01,2026-01-07,enrollment,8,50\n"
        )
        gw = ShadowGateway(k_min=10)
        result = gw.ingest_csv(csv_content)
        assert result.admitted
        assert result.receipt is not None
        assert result.receipt.suppressed_cells >= 1
        assert result.rows[0]["site_count"] is None

    def test_non_aggregate_patient_fields_rejected(self) -> None:
        csv_content = (
            "week_start,week_end,metric_name,patient_id,diagnosis\n"
            "2026-01-01,2026-01-07,enrollment,P001,asthma\n"
        )
        gw = ShadowGateway()
        result = gw.ingest_csv(csv_content)
        assert result.status == ShadowIngestionStatus.REJECTED_NON_AGGREGATE
        assert result.reason_code == "GW-CLIN-002"

    def test_invalid_csv_format_rejected(self) -> None:
        gw = ShadowGateway()
        result = gw.ingest_csv("not,a valid\nbroken,csv\n")
        # Should be admitted if columns match, or rejected if they don't
        # Let's test with truly invalid format
        result = gw.ingest_csv("{invalid json}")
        assert result.status in (
            ShadowIngestionStatus.REJECTED_INVALID_FORMAT,
            ShadowIngestionStatus.REJECTED_UNKNOWN_COLUMNS,
        )


class TestShadowGatewayJSON:
    """G13.4: Shadow ingestion with JSON input."""

    def test_valid_json_admitted(self) -> None:
        json_content = json.dumps(
            [
                {
                    "week_start": "2026-01-01",
                    "week_end": "2026-01-07",
                    "metric_name": "enrollment",
                    "site_count": 10,
                    "enrollment_count": 50,
                    "predicted_value": 45,
                    "actual_value": 48,
                },
                {
                    "week_start": "2026-01-08",
                    "week_end": "2026-01-14",
                    "metric_name": "enrollment",
                    "site_count": 12,
                    "enrollment_count": 55,
                    "predicted_value": 50,
                    "actual_value": 52,
                },
            ]
        )
        gw = ShadowGateway()
        result = gw.ingest_json(json_content)
        assert result.admitted
        assert result.receipt is not None
        assert result.receipt.row_count == 2

    def test_json_with_rows_key(self) -> None:
        json_content = json.dumps(
            {
                "rows": [
                    {
                        "week_start": "2026-01-01",
                        "week_end": "2026-01-07",
                        "metric_name": "enrollment",
                        "site_count": 10,
                    }
                ]
            }
        )
        gw = ShadowGateway()
        result = gw.ingest_json(json_content)
        assert result.admitted

    def test_json_unknown_columns_rejected(self) -> None:
        json_content = json.dumps(
            [
                {
                    "week_start": "2026-01-01",
                    "week_end": "2026-01-07",
                    "metric_name": "enrollment",
                    "evil_field": "bad",
                }
            ]
        )
        gw = ShadowGateway()
        result = gw.ingest_json(json_content)
        assert result.status == ShadowIngestionStatus.REJECTED_UNKNOWN_COLUMNS


class TestShadowGatewayReceipt:
    """G13.4: Receipts are hashed and stored."""

    def test_receipt_has_hash(self) -> None:
        csv_content = (
            "week_start,week_end,metric_name,site_count\n"
            "2026-01-01,2026-01-07,enrollment,10\n"
        )
        gw = ShadowGateway()
        result = gw.ingest_csv(csv_content)
        assert result.admitted
        assert result.receipt is not None
        assert len(result.receipt.input_hash) == 64
        assert result.receipt.receipt_id  # non-empty

    def test_receipt_persisted_to_dir(self, tmp_path: Path) -> None:
        csv_content = (
            "week_start,week_end,metric_name,site_count\n"
            "2026-01-01,2026-01-07,enrollment,10\n"
        )
        receipts_dir = tmp_path / "receipts"
        gw = ShadowGateway(receipts_dir=receipts_dir)
        result = gw.ingest_csv(csv_content)
        assert result.admitted
        assert result.receipt is not None
        receipt_file = receipts_dir / f"{result.receipt.receipt_id}.json"
        assert receipt_file.exists()

    def test_receipt_contains_forecast_vs_actual(self) -> None:
        json_content = json.dumps(
            [
                {
                    "week_start": "2026-01-01",
                    "week_end": "2026-01-07",
                    "metric_name": "enrollment",
                    "site_count": 10,
                    "predicted_value": 45,
                    "actual_value": 48,
                },
            ]
        )
        gw = ShadowGateway()
        result = gw.ingest_json(json_content)
        assert result.admitted
        assert result.receipt is not None
        fvsa = result.receipt.forecast_vs_actual
        assert "comparisons" in fvsa
        assert fvsa["count"] == 1
        comp = fvsa["comparisons"][0]
        assert comp["predicted"] == 45
        assert comp["actual"] == 48
        assert comp["difference"] == 3

    def test_no_free_text_interpretation(self) -> None:
        """Receipts must not contain free-text clinical interpretation."""
        json_content = json.dumps(
            [
                {
                    "week_start": "2026-01-01",
                    "week_end": "2026-01-07",
                    "metric_name": "enrollment",
                    "site_count": 10,
                    "predicted_value": 45,
                    "actual_value": 48,
                },
            ]
        )
        gw = ShadowGateway()
        result = gw.ingest_json(json_content)
        assert result.admitted
        assert result.receipt is not None
        receipt_str = json.dumps(result.receipt.model_dump())
        # Must not contain free-text clinical interpretation
        forbidden = [
            "diagnosis",
            "prognosis",
            "treatment",
            "clinical assessment",
            "patient outcome",
        ]
        for term in forbidden:
            assert term not in receipt_str.lower(), (
                f"free-text clinical term '{term}' found in receipt"
            )


class TestShadowGatewayConfig:
    """G13.4: Configuration validation."""

    def test_default_k_min_is_5(self) -> None:
        assert DEFAULT_K_MIN == 5

    def test_k_min_must_be_positive(self) -> None:
        with pytest.raises(ShadowIngestionError):
            ShadowGateway(k_min=0)

    def test_allowed_columns_match_contract(self) -> None:
        gw = ShadowGateway()
        assert "week_start" in gw.allowed_columns
        assert "patient_id" not in gw.allowed_columns
        assert len(DATA_CONTRACT_V1_COLUMNS) > 5

    def test_ingest_file_csv(self, tmp_path: Path) -> None:
        f = tmp_path / "test.csv"
        f.write_text(
            "week_start,week_end,metric_name,site_count\n"
            "2026-01-01,2026-01-07,enrollment,10\n",
            encoding="utf-8",
        )
        gw = ShadowGateway()
        result = gw.ingest_file(f)
        assert result.admitted

    def test_ingest_file_json(self, tmp_path: Path) -> None:
        f = tmp_path / "test.json"
        f.write_text(
            json.dumps(
                [
                    {
                        "week_start": "2026-01-01",
                        "week_end": "2026-01-07",
                        "metric_name": "enrollment",
                        "site_count": 10,
                    }
                ]
            ),
            encoding="utf-8",
        )
        gw = ShadowGateway()
        result = gw.ingest_file(f)
        assert result.admitted

    def test_ingest_file_unknown_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("some content", encoding="utf-8")
        gw = ShadowGateway()
        result = gw.ingest_file(f)
        assert result.status == ShadowIngestionStatus.REJECTED_INVALID_FORMAT

    def test_ingest_file_nonexistent_raises(self) -> None:
        gw = ShadowGateway()
        with pytest.raises(ShadowIngestionError):
            gw.ingest_file(Path("/nonexistent/file.csv"))
