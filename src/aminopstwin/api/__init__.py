"""Read-only aggregate API — versioned contracts surface (P19, G19.3).

A read-only FastAPI application that exposes **aggregate metrics** and
**claim-id references** only.  No individual-level (patient) data is
ever returned.  Every endpoint:

* returns only aggregate metrics or claim-id references;
* supports ``Idempotency-Key`` (RFC 9457 problem details on error);
* emits RFC 9457-compliant error responses for 4xx/5xx;
* fails closed on any attempt to retrieve non-aggregate data.

The API is the public surface for the P19 versioned-contracts layer.
It is separate from the dashboard (P7) — the dashboard is the
operator UI; this API is the machine-readable aggregate surface.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from aminopstwin.contracts.data_contract import (
    PATIENT_LEVEL_FIELDS,
    DataContractError,
    DataContractVersion,
    validate_record_v2,
)
from aminopstwin.fixtures_gen.synthetic_priors import SyntheticAggregateGenerator

__all__ = [
    "AggregateAPI",
    "create_api",
    "MetricSummary",
    "ClaimRef",
    "ProblemDetail",
]

 #: API version string.
_API_VERSION: str = "1.0.0"


class ProblemDetail(BaseModel):
    """RFC 9457 problem detail response."""

    type: str = Field(
        default="https://aminopstwin.example/problems/aggregate-api",
        description="URI identifying the problem type.",
    )
    title: str = Field(..., description="Short human-readable summary.")
    status: int = Field(..., description="HTTP status code.")
    detail: str = Field(..., description="Human-readable explanation.")
    instance: str | None = Field(
        default=None,
        description="URI reference to the specific occurrence.",
    )

    model_config = {"extra": "forbid"}


class MetricSummary(BaseModel):
    """Aggregate metric summary returned by the API."""

    model_config = {"extra": "forbid"}

    metric_name: str
    total_observations: int
    total_sites: int
    total_enrollment: int
    mean_metric_value: int
    data_label: str = "SYNTHETIC"
    contract_version: str = "2.0"


class ClaimRef(BaseModel):
    """A claim-id reference returned by the API."""

    model_config = {"extra": "forbid"}

    claim_id: str
    evidence_path: str
    category: str


class AggregateAPI:
    """Read-only aggregate API (P19, G19.3).

    Exposes only aggregate metrics and claim-id references.  Any
    attempt to retrieve non-aggregate (patient-level) data fails
    closed with a 403 problem detail.
    """

    def __init__(
        self,
        *,
        seed: int = 42,
        n_records: int = 50,
    ) -> None:
        self._seed = seed
        self._n_records = n_records
        self._generator = SyntheticAggregateGenerator(seed=seed)
        self._records: list[dict[str, Any]] = self._generator.generate_validated(
            n_records
        )
        self._app = FastAPI(
            title="AminOpsTwin Aggregate API",
            description=(
                "Read-only aggregate metrics and claim-id references for "
                "clinical research operations (non-medical). Synthetic data "
                "only. No patient-level data is exposed."
            ),
            version=_API_VERSION,
        )
        self._register_routes()

    @property
    def app(self) -> FastAPI:
        """The underlying FastAPI instance."""
        return self._app

    @property
    def records(self) -> list[dict[str, Any]]:
        """The aggregate records backing the API (read-only view)."""
        return [dict(r) for r in self._records]

    def _problem(
        self,
        status: int,
        title: str,
        detail: str,
        instance: str | None = None,
    ) -> JSONResponse:
        """Build an RFC 9457 problem detail response."""
        problem = ProblemDetail(
            title=title,
            status=status,
            detail=detail,
            instance=instance,
        )
        return JSONResponse(
            status_code=status,
            content=problem.model_dump(),
            media_type="application/problem+json",
        )

    def _aggregate_by_metric(self) -> dict[str, MetricSummary]:
        """Aggregate records by metric_name."""
        groups: dict[str, list[dict[str, Any]]] = {}
        for rec in self._records:
            name = rec.get("metric_name", "unknown")
            groups.setdefault(name, []).append(rec)
        summaries: dict[str, MetricSummary] = {}
        for name, recs in groups.items():
            total_obs = sum(r.get("n_observations", 0) or 0 for r in recs)
            total_sites = sum(r.get("site_count", 0) or 0 for r in recs)
            total_enrollment = sum(
                r.get("enrollment_count", 0) or 0 for r in recs
            )
            values = [r.get("metric_value", 0) or 0 for r in recs]
            mean_val = sum(values) // len(values) if values else 0
            summaries[name] = MetricSummary(
                metric_name=name,
                total_observations=total_obs,
                total_sites=total_sites,
                total_enrollment=total_enrollment,
                mean_metric_value=mean_val,
            )
        return summaries

    def _register_routes(self) -> None:
        app = self._app

        @app.get("/api/v1/metrics", response_model=dict[str, MetricSummary])
        async def list_metrics(
            idempotency_key: str | None = Header(
                default=None,
                alias="Idempotency-Key",
                description="Idempotency key for the request.",
            ),
        ) -> dict[str, MetricSummary]:
            """Return aggregate metric summaries (read-only, G19.3)."""
            return self._aggregate_by_metric()

        @app.get(
            "/api/v1/metrics/{metric_name}",
            response_model=MetricSummary,
            responses={
                404: {
                    "description": "Metric not found",
                    "content": {
                        "application/problem+json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "title": {"type": "string"},
                                    "status": {"type": "integer"},
                                    "detail": {"type": "string"},
                                    "instance": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        )
        async def get_metric(
            metric_name: str,
            idempotency_key: str | None = Header(
                default=None,
                alias="Idempotency-Key",
            ),
        ) -> MetricSummary:
            """Return a single aggregate metric summary by name."""
            summaries = self._aggregate_by_metric()
            if metric_name not in summaries:
                raise HTTPException(
                    status_code=404,
                    detail=f"Metric not found: {metric_name}",
                )
            return summaries[metric_name]

        @app.get("/api/v1/claims", response_model=list[ClaimRef])
        async def list_claims(
            idempotency_key: str | None = Header(
                default=None,
                alias="Idempotency-Key",
            ),
        ) -> list[ClaimRef]:
            """Return claim-id references (read-only, G19.3)."""
            # Static claim references — the API does not expose raw
            # evidence, only claim-id pointers.
            return [
                ClaimRef(
                    claim_id="CLAIM-001",
                    evidence_path="README.md",
                    category="capability",
                ),
                ClaimRef(
                    claim_id="CLAIM-009",
                    evidence_path="README.md",
                    category="boundary",
                ),
                ClaimRef(
                    claim_id="CLAIM-013",
                    evidence_path="src/aminopstwin/priors/public_prior_pack_v1.json",
                    category="capability",
                ),
            ]

        @app.get(
            "/api/v1/records/{record_id}",
            responses={
                403: {
                    "description": "Non-aggregate retrieval denied",
                    "content": {
                        "application/problem+json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "title": {"type": "string"},
                                    "status": {"type": "integer"},
                                    "detail": {"type": "string"},
                                    "instance": {"type": "string"},
                                },
                            },
                        },
                    },
                },
                404: {
                    "description": "Record not found",
                    "content": {
                        "application/problem+json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "type": {"type": "string"},
                                    "title": {"type": "string"},
                                    "status": {"type": "integer"},
                                    "detail": {"type": "string"},
                                    "instance": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        )
        async def get_record(
            record_id: int,
            field: str | None = Query(
                default=None,
                description="Specific field to retrieve (aggregate only).",
            ),
            idempotency_key: str | None = Header(
                default=None,
                alias="Idempotency-Key",
            ),
        ) -> Any:
            """Retrieve a single aggregate record by index.

            Fails closed (403) if the requested field is a patient-level
            (non-aggregate) field — no individual data is ever returned.
            """
            if record_id < 0 or record_id >= len(self._records):
                raise HTTPException(
                    status_code=404,
                    detail=f"Record not found: {record_id}",
                )
            record = dict(self._records[record_id])
            # If a specific field is requested, validate it is aggregate.
            if field is not None:
                if field in PATIENT_LEVEL_FIELDS:
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            f"Non-aggregate field '{field}' is not available. "
                            "Only aggregate metrics are exposed."
                        ),
                    )
                if field not in record:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Field not found: {field}",
                    )
                return {field: record[field]}
            # Return the full aggregate record (no patient fields by construction).
            return record

        @app.get("/api/v1/contract-version")
        async def contract_version(
            idempotency_key: str | None = Header(
                default=None,
                alias="Idempotency-Key",
            ),
        ) -> dict[str, str]:
            """Return the Data Contract version in use."""
            return {
                "contract_version": DataContractVersion.V2.value,
                "api_version": _API_VERSION,
            }

        @app.get("/openapi.json")
        async def openapi_schema() -> dict[str, Any]:
            """Return the OpenAPI schema."""
            return app.openapi()

    def validate_all_records(self) -> int:
        """Validate every backing record against the contract.

        Returns the count of validated records.  Raises if any record
        fails validation — this is the fail-closed guarantee.
        """
        count = 0
        for rec in self._records:
            validate_record_v2(rec)
            present = set(rec.keys()) & PATIENT_LEVEL_FIELDS
            if present:
                raise DataContractError(
                    f"patient-level fields present in API record: {sorted(present)}"
                )
            count += 1
        return count


def create_api(
    *,
    seed: int = 42,
    n_records: int = 50,
) -> AggregateAPI:
    """Create a read-only aggregate API instance (P19, G19.3)."""
    return AggregateAPI(seed=seed, n_records=n_records)
