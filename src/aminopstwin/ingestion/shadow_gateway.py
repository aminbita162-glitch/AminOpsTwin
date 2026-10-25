"""Shadow-Mode Ingestion Gateway with Data Contract v1 (Idea S3, P13, G13.4).

A dedicated ingestion path that accepts only weekly aggregate CSV or JSON
files under a strict Data Contract v1.  Enforces schema validation, rejects
unknown columns, applies k-min cell suppression (default k=5), and produces
a hashed receipt.  Output is limited to aggregate forecast-vs-actual
comparison; no free-text clinical interpretation is produced.

Security rules:
- Only aggregate columns are accepted (no patient-level fields).
- Unknown columns are rejected (GW-INJ-002 / GW-SCHEMA-006).
- Cell suppression: any cell with k < k_min contributing observations
  is suppressed (replaced with None) and recorded in the receipt.
- Receipts are SHA-256 hashed and stored under test_home/P13/receipts/.
- No free-text clinical interpretation is emitted.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import io
import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ShadowIngestionError",
    "ShadowIngestionResult",
    "ShadowIngestionStatus",
    "ShadowGateway",
    "Receipt",
    "DATA_CONTRACT_V1_COLUMNS",
]

#: Default k-min for cell suppression.
DEFAULT_K_MIN: int = 5

#: Data Contract v1 — the only allowed columns in a weekly aggregate file.
#: Each column has a type and a flag indicating whether it is a count
#: used for k-min suppression.
DATA_CONTRACT_V1_COLUMNS: dict[str, dict[str, str | bool]] = {
    "week_start": {"type": "date", "count_column": False},
    "week_end": {"type": "date", "count_column": False},
    "metric_name": {"type": "str", "count_column": False},
    "metric_value": {"type": "int", "count_column": False},
    "site_count": {"type": "int", "count_column": True},
    "enrollment_count": {"type": "int", "count_column": True},
    "active_sites": {"type": "int", "count_column": True},
    "predicted_value": {"type": "int", "count_column": False},
    "actual_value": {"type": "int", "count_column": False},
    "variance": {"type": "int", "count_column": False},
    "n_observations": {"type": "int", "count_column": True},
}

#: Columns whose values are counts used for k-min suppression.
COUNT_COLUMNS: frozenset[str] = frozenset(
    k for k, v in DATA_CONTRACT_V1_COLUMNS.items() if v.get("count_column", False)
)

#: Required columns (must be present in every aggregate file).
REQUIRED_COLUMNS: frozenset[str] = frozenset({"week_start", "week_end", "metric_name"})


class ShadowIngestionError(Exception):
    """Raised when the shadow ingestion encounters a configuration error."""


class ShadowIngestionStatus(StrEnum):
    """Outcome of a shadow ingestion attempt."""

    ADMITTED = "ADMITTED"
    REJECTED_UNKNOWN_COLUMNS = "REJECTED_UNKNOWN_COLUMNS"
    REJECTED_MISSING_REQUIRED = "REJECTED_MISSING_REQUIRED"
    REJECTED_INVALID_FORMAT = "REJECTED_INVALID_FORMAT"
    REJECTED_NON_AGGREGATE = "REJECTED_NON_AGGREGATE"
    REJECTED_TOO_FEW_ROWS = "REJECTED_TOO_FEW_ROWS"
    REJECTED_EMPTY = "REJECTED_EMPTY"


class Receipt(BaseModel):
    """A hashed receipt for a shadow ingestion (G13.4)."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    receipt_id: str
    status: ShadowIngestionStatus
    reason_code: str
    input_hash: str
    row_count: int
    suppressed_cells: int
    suppressed_details: list[dict[str, Any]] = Field(default_factory=list)
    k_min: int
    ingested_at: str
    file_format: str
    forecast_vs_actual: dict[str, Any] = Field(default_factory=dict)


class ShadowIngestionResult(BaseModel):
    """Result of a shadow ingestion (G13.4)."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    status: ShadowIngestionStatus
    reason_code: str
    receipt: Receipt | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def admitted(self) -> bool:
        return self.status == ShadowIngestionStatus.ADMITTED


class ShadowGateway:
    """Shadow-mode ingestion gateway with Data Contract v1 (Idea S3, P13).

    Accepts only weekly aggregate CSV or JSON files.  Enforces schema,
    rejects unknown columns, applies k-min cell suppression, and emits
    a hashed receipt.
    """

    def __init__(
        self,
        receipts_dir: Path | None = None,
        k_min: int = DEFAULT_K_MIN,
    ) -> None:
        if k_min < 1:
            raise ShadowIngestionError(
                f"k_min must be >= 1, got {k_min}"
            )
        self._k_min = k_min
        self._receipts_dir = receipts_dir

    @property
    def k_min(self) -> int:
        return self._k_min

    @property
    def allowed_columns(self) -> frozenset[str]:
        return frozenset(DATA_CONTRACT_V1_COLUMNS.keys())

    def ingest_csv(self, content: str) -> ShadowIngestionResult:
        """Ingest a weekly aggregate CSV string."""
        return self._ingest(content, file_format="csv")

    def ingest_json(self, content: str) -> ShadowIngestionResult:
        """Ingest a weekly aggregate JSON string."""
        return self._ingest(content, file_format="json")

    def ingest_file(self, path: Path) -> ShadowIngestionResult:
        """Ingest a file (detected by extension)."""
        if not path.exists():
            raise ShadowIngestionError(f"file not found: {path}")
        content = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".csv":
            return self._ingest(content, file_format="csv")
        if path.suffix.lower() in (".json", ".jsonl"):
            return self._ingest(content, file_format="json")
        return self._reject(
            content,
            ShadowIngestionStatus.REJECTED_INVALID_FORMAT,
            "GW-INJ-002",
            file_format="unknown",
            rows=[],
            row_count=0,
            suppressed=0,
            suppressed_details=[],
        )

    def _ingest(self, content: str, file_format: str) -> ShadowIngestionResult:
        """Parse and validate content, then apply k-min suppression."""
        if not content.strip():
            return self._reject(
                content,
                ShadowIngestionStatus.REJECTED_EMPTY,
                "GW-INJ-002",
                file_format,
                [],
                0,
                0,
                [],
            )

        rows: list[dict[str, Any]]
        try:
            if file_format == "csv":
                rows = self._parse_csv(content)
            else:
                rows = self._parse_json(content)
        except ShadowIngestionError:
            raise
        except (json.JSONDecodeError, csv.Error, ValueError) as exc:
            return self._reject(
                content,
                ShadowIngestionStatus.REJECTED_INVALID_FORMAT,
                "GW-INJ-002",
                file_format,
                [],
                0,
                0,
                [],
                detail=str(exc),
            )

        if not rows:
            return self._reject(
                content,
                ShadowIngestionStatus.REJECTED_EMPTY,
                "GW-INJ-002",
                file_format,
                [],
                0,
                0,
                [],
            )

        # Check for patient-level / non-aggregate fields BEFORE column
        # validation so that patient data is never silently admitted.
        all_cols: set[str] = set()
        for r in rows:
            all_cols.update(r.keys())

        patient_fields = frozenset(
            {
                "patient_id",
                "patient_name",
                "diagnosis",
                "prognosis",
                "treatment",
                "dose",
                "individual_risk",
                "health_status",
            }
        )
        if all_cols & patient_fields:
            return self._reject(
                content,
                ShadowIngestionStatus.REJECTED_NON_AGGREGATE,
                "GW-CLIN-002",
                file_format,
                rows,
                len(rows),
                0,
                [],
                detail=(
                    f"patient-level columns detected: "
                    f"{sorted(all_cols & patient_fields)}"
                ),
            )

        # Validate columns against Data Contract v1
        unknown = all_cols - self.allowed_columns
        if unknown:
            return self._reject(
                content,
                ShadowIngestionStatus.REJECTED_UNKNOWN_COLUMNS,
                "GW-SCHEMA-006",
                file_format,
                rows,
                len(rows),
                0,
                [],
                detail=f"unknown columns: {sorted(unknown)}",
            )

        missing = REQUIRED_COLUMNS - all_cols
        if missing:
            return self._reject(
                content,
                ShadowIngestionStatus.REJECTED_MISSING_REQUIRED,
                "GW-SCHEMA-006",
                file_format,
                rows,
                len(rows),
                0,
                [],
                detail=f"missing required columns: {sorted(missing)}",
            )

        # Type validation
        validated_rows: list[dict[str, Any]] = []
        for r in rows:
            vr = self._validate_row_types(r)
            validated_rows.append(vr)

        # K-min cell suppression
        suppressed_details: list[dict[str, Any]] = []
        for r in validated_rows:
            for col in COUNT_COLUMNS:
                if col in r:
                    val = r[col]
                    if isinstance(val, int) and val < self._k_min:
                        suppressed_details.append(
                            {
                                "column": col,
                                "week_start": r.get("week_start"),
                                "original_value": val,
                                "reason": f"count {val} < k_min {self._k_min}",
                            }
                        )
                        r[col] = None  # suppress

        # Compute forecast-vs-actual comparison (aggregate only)
        forecast_vs_actual = self._compute_forecast_vs_actual(validated_rows)

        # Build receipt
        input_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        receipt_id = hashlib.sha256(
            f"{input_hash}:{_dt.datetime.now(_dt.UTC).isoformat()}".encode()
        ).hexdigest()[:16]
        ingested_at = _dt.datetime.now(_dt.UTC).isoformat()

        receipt = Receipt(
            receipt_id=receipt_id,
            status=ShadowIngestionStatus.ADMITTED,
            reason_code="",
            input_hash=input_hash,
            row_count=len(validated_rows),
            suppressed_cells=len(suppressed_details),
            suppressed_details=suppressed_details,
            k_min=self._k_min,
            ingested_at=ingested_at,
            file_format=file_format,
            forecast_vs_actual=forecast_vs_actual,
        )

        # Persist receipt
        if self._receipts_dir is not None:
            self._persist_receipt(receipt)

        return ShadowIngestionResult(
            status=ShadowIngestionStatus.ADMITTED,
            reason_code="",
            receipt=receipt,
            rows=validated_rows,
        )

    def _reject(
        self,
        content: str,
        status: ShadowIngestionStatus,
        reason_code: str,
        file_format: str,
        rows: list[dict[str, Any]],
        row_count: int,
        suppressed: int,
        suppressed_details: list[dict[str, Any]],
        detail: str = "",
    ) -> ShadowIngestionResult:
        """Build a rejection result with a receipt."""
        input_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        receipt_id = hashlib.sha256(
            f"{input_hash}:{status.value}".encode()
        ).hexdigest()[:16]
        ingested_at = _dt.datetime.now(_dt.UTC).isoformat()
        receipt = Receipt(
            receipt_id=receipt_id,
            status=status,
            reason_code=reason_code,
            input_hash=input_hash,
            row_count=row_count,
            suppressed_cells=suppressed,
            suppressed_details=suppressed_details,
            k_min=self._k_min,
            ingested_at=ingested_at,
            file_format=file_format,
            forecast_vs_actual={"detail": detail} if detail else {},
        )
        return ShadowIngestionResult(
            status=status,
            reason_code=reason_code,
            receipt=receipt,
            rows=rows,
        )

    def _persist_receipt(self, receipt: Receipt) -> Path | None:
        """Persist a receipt to the receipts directory."""
        if self._receipts_dir is None:
            return None
        self._receipts_dir.mkdir(parents=True, exist_ok=True)
        path = self._receipts_dir / f"{receipt.receipt_id}.json"
        path.write_text(
            json.dumps(receipt.model_dump(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def _parse_csv(content: str) -> list[dict[str, Any]]:
        """Parse CSV content into a list of dicts."""
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            raise ValueError("empty CSV: no data rows")
        # Convert numeric strings
        for r in rows:
            for col in DATA_CONTRACT_V1_COLUMNS:
                if col in r and r[col] is not None and r[col] != "":
                    meta = DATA_CONTRACT_V1_COLUMNS[col]
                    if meta["type"] == "int":
                        r[col] = int(r[col])
        return rows

    @staticmethod
    def _parse_json(content: str) -> list[dict[str, Any]]:
        """Parse JSON content into a list of dicts (array or {rows: [...]})."""
        data = json.loads(content)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and "rows" in data:
            rows = data["rows"]
        else:
            raise ValueError("JSON must be an array or {\"rows\": [...]}")
        if not isinstance(rows, list):
            raise ValueError("rows must be a list")
        return rows

    @staticmethod
    def _validate_row_types(row: dict[str, Any]) -> dict[str, Any]:
        """Validate and coerce row types against the Data Contract."""
        result: dict[str, Any] = {}
        for col, val in row.items():
            if col not in DATA_CONTRACT_V1_COLUMNS:
                continue
            meta = DATA_CONTRACT_V1_COLUMNS[col]
            col_type = meta["type"]
            if val is None or val == "":
                result[col] = None
                continue
            if col_type == "int":
                if isinstance(val, str):
                    val = int(val)
                result[col] = int(val)
            elif col_type == "str" or col_type == "date":
                result[col] = str(val)
            else:
                result[col] = val
        return result

    @staticmethod
    def _compute_forecast_vs_actual(
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Compute aggregate forecast-vs-actual comparison (no free-text)."""
        comparisons: list[dict[str, Any]] = []
        for r in rows:
            pred = r.get("predicted_value")
            actual = r.get("actual_value")
            if pred is not None and actual is not None:
                diff = actual - pred
                pct_error = (
                    round(100 * diff / pred, 2) if pred != 0 else None
                )
                comparisons.append(
                    {
                        "week_start": r.get("week_start"),
                        "metric_name": r.get("metric_name"),
                        "predicted": pred,
                        "actual": actual,
                        "difference": diff,
                        "pct_error": pct_error,
                    }
                )
        return {
            "comparisons": comparisons,
            "count": len(comparisons),
        }
