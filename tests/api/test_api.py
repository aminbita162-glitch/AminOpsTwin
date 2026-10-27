"""G19.3 — Read-only API aggregate-only enforced (P19).

Tests:
  - the API returns only aggregate metrics and claim-id references;
  - Idempotency-Key header is accepted;
  - OpenAPI schema is available;
  - RFC 9457 problem details are emitted on error;
  - a negative test: attempting to retrieve a non-aggregate
    (patient-level) field fails closed with 403.
"""

from __future__ import annotations

from aminopstwin.api import create_api
from fastapi.testclient import TestClient


class TestAggregateAPI:
    """The read-only aggregate API exposes only aggregate data."""

    def setup_method(self) -> None:
        self.api = create_api(seed=42, n_records=20)
        self.client = TestClient(self.api.app)

    def test_list_metrics(self) -> None:
        resp = self.client.get("/api/v1/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        # Each value is a MetricSummary with aggregate fields.
        for summary in data.values():
            assert "metric_name" in summary
            assert "total_observations" in summary
            assert "data_label" in summary
            assert summary["data_label"] == "SYNTHETIC"

    def test_get_metric_by_name(self) -> None:
        resp = self.client.get("/api/v1/metrics/enrollment_rate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric_name"] == "enrollment_rate"

    def test_get_metric_not_found(self) -> None:
        resp = self.client.get("/api/v1/metrics/nonexistent")
        assert resp.status_code == 404

    def test_list_claims(self) -> None:
        resp = self.client.get("/api/v1/claims")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for claim in data:
            assert "claim_id" in claim
            assert "evidence_path" in claim
            assert "category" in claim

    def test_contract_version(self) -> None:
        resp = self.client.get("/api/v1/contract-version")
        assert resp.status_code == 200
        data = resp.json()
        assert data["contract_version"] == "2.0"

    def test_openapi_schema_available(self) -> None:
        resp = self.client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "openapi" in schema
        assert "paths" in schema

    def test_idempotency_key_accepted(self) -> None:
        resp = self.client.get(
            "/api/v1/metrics",
            headers={"Idempotency-Key": "test-key-1234567890abcdef"},
        )
        assert resp.status_code == 200


class TestAggregateOnlyNegative:
    """Negative test: non-aggregate retrieval fails closed (G19.3)."""

    def setup_method(self) -> None:
        self.api = create_api(seed=42, n_records=20)
        self.client = TestClient(self.api.app)

    def test_patient_field_retrieval_denied(self) -> None:
        """Retrieving a patient-level field returns 403, never the data."""
        resp = self.client.get("/api/v1/records/0?field=patient_id")
        assert resp.status_code == 403
        # The body should be an RFC 9457 problem detail.
        body = resp.json()
        assert "detail" in body or "title" in body

    def test_patient_name_field_denied(self) -> None:
        resp = self.client.get("/api/v1/records/0?field=patient_name")
        assert resp.status_code == 403

    def test_diagnosis_field_denied(self) -> None:
        resp = self.client.get("/api/v1/records/0?field=diagnosis")
        assert resp.status_code == 403

    def test_aggregate_field_allowed(self) -> None:
        """Aggregate fields are returned normally."""
        resp = self.client.get("/api/v1/records/0?field=metric_value")
        assert resp.status_code == 200
        data = resp.json()
        assert "metric_value" in data

    def test_full_record_has_no_patient_fields(self) -> None:
        """A full record response contains no patient-level fields."""
        resp = self.client.get("/api/v1/records/0")
        assert resp.status_code == 200
        data = resp.json()
        patient_fields = {
            "patient_id",
            "patient_name",
            "diagnosis",
            "prognosis",
            "treatment",
            "dose",
            "individual_risk",
            "health_status",
        }
        assert not (set(data.keys()) & patient_fields)

    def test_record_not_found(self) -> None:
        resp = self.client.get("/api/v1/records/99999")
        assert resp.status_code == 404

    def test_all_records_aggregate_only(self) -> None:
        """Every record exposed by the API is aggregate-only."""
        for i in range(20):
            resp = self.client.get(f"/api/v1/records/{i}")
            assert resp.status_code == 200
            data = resp.json()
            patient_fields = {
                "patient_id",
                "patient_name",
                "diagnosis",
                "prognosis",
                "treatment",
                "dose",
                "individual_risk",
                "health_status",
            }
            assert not (set(data.keys()) & patient_fields), (
                f"record {i} has patient fields: "
                f"{set(data.keys()) & patient_fields}"
            )


class TestAPIValidation:
    """The API's backing records all validate against the contract."""

    def test_validate_all_records(self) -> None:
        api = create_api(seed=42, n_records=30)
        count = api.validate_all_records()
        assert count == 30
