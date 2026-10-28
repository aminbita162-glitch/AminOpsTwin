"""Evaluation harness for all implemented capabilities (P8, G5.4).

Runs every implemented capability and records pass/fail with measured
values.  The harness produces a report suitable for the evidence pack.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aminopstwin.contracts.canonical import canonical_hash
from aminopstwin.contracts.clock import SeededClock
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.enterprise.tenant import TenantGuard, TenantScope
from aminopstwin.executor.memory import MemoryClass, MemoryStore
from aminopstwin.gateway.gateway import PolicyGateway, PolicyMatrix, PolicyMatrixEntry
from aminopstwin.tokens.budget import BudgetGovernor, BudgetLevel
from aminopstwin.twin.pipeline import TokenPipeline
from aminopstwin.twin.scenarios import load_default_scenarios
from aminopstwin.twin.simulation import ScenarioConfig, SimulationEngine

__all__ = [
    "CapabilityResult",
    "EvaluationHarness",
    "EvaluationReport",
]


@dataclass(frozen=True)
class CapabilityResult:
    """Result of evaluating a single capability."""

    capability_id: str
    name: str
    status: str   # PASS | FAIL | NOT_RUN
    measured_value: Any
    duration_ms: float
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "status": self.status,
            "measured_value": self.measured_value,
            "duration_ms": self.duration_ms,
            "detail": self.detail,
        }


@dataclass
class EvaluationReport:
    """Report of evaluating all implemented capabilities."""

    results: list[CapabilityResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    not_run: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "not_run": self.not_run,
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )


@dataclass
class EvaluationHarness:
    """Evaluation harness that tests every implemented capability (G5.4).

    Each capability is exercised with a synthetic fixture and the
    result (PASS/FAIL) is recorded with a measured value.
    """

    def _eval_schema_validation(self) -> CapabilityResult:
        """Evaluate schema validation (R03)."""
        import uuid

        clock = SeededClock()
        payload = {"test": "value", "count": 42}
        payload_hash = canonical_hash(payload)
        envelope = Envelope(
            envelope_version="1.0",
            schema_id="test.eval@1",
            envelope_type="test",
            correlation_id=uuid.uuid4(),
            causation_id=None,
            tenant_id="tenant-test",
            policy_epoch=0,
            idempotency_key="eval-schema-validation-key-001",
            payload=payload,
            payload_hash=payload_hash,
            created_at=clock.now(),
        )
        ok = envelope.schema_id == "test.eval@1"
        return CapabilityResult(
            capability_id="R03",
            name="Schema validation",
            status="PASS" if ok else "FAIL",
            measured_value=ok,
            duration_ms=0.0,
            detail="Envelope schema validation produces valid envelope",
        )

    def _eval_policy_gateway(self) -> CapabilityResult:
        """Evaluate policy gateway (R04)."""
        import uuid

        clock = SeededClock()
        matrix = PolicyMatrix()
        matrix.add(PolicyMatrixEntry("A1", "test", "default"))
        gw = PolicyGateway(
            policy_matrix=matrix,
            current_epoch=0,
            schema_registry={"test.eval@1"},
            envelope_type_registry={"test.eval@1": "test"},
        )
        payload = {"test": "value"}
        envelope = Envelope(
            envelope_version="1.0",
            schema_id="test.eval@1",
            envelope_type="test",
            correlation_id=uuid.uuid4(),
            causation_id=None,
            tenant_id="tenant-test",
            policy_epoch=0,
            idempotency_key="eval-gateway-allow-key-000001",
            payload=payload,
            payload_hash=canonical_hash(payload),
            created_at=clock.now(),
        )
        decision = gw.evaluate(envelope, "A1", clock.now(), "default")
        ok = decision.decision.value == "ALLOW"
        return CapabilityResult(
            capability_id="R04",
            name="Policy Gateway evaluation",
            status="PASS" if ok else "FAIL",
            measured_value=decision.decision.value,
            duration_ms=0.0,
            detail=f"Gateway returned {decision.decision.value}",
        )

    def _eval_budget_governor(self) -> CapabilityResult:
        """Evaluate budget governor (R15)."""
        gov = BudgetGovernor(100, 100, 100)
        ok = gov.reserve(BudgetLevel.SESSION, 50)
        remaining = gov.remaining(BudgetLevel.SESSION)
        return CapabilityResult(
            capability_id="R15",
            name="Budget governor",
            status="PASS" if ok else "FAIL",
            measured_value=remaining,
            duration_ms=0.0,
            detail=f"Reserved 50, remaining={remaining}",
        )

    def _eval_simulation(self) -> CapabilityResult:
        """Evaluate simulation engine (R12)."""
        config = ScenarioConfig(
            scenario_id="eval-sim-001",
            seed=42,
            num_sites=2,
            num_resources_per_site=3,
            num_queues_per_site=1,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=5.0,
            mean_service_time=10,
            sim_duration=100,
        )
        engine = SimulationEngine(config)
        result = engine.run()
        ok = result.final_state_hash != ""
        return CapabilityResult(
            capability_id="R12",
            name="Simulation engine",
            status="PASS" if ok else "FAIL",
            measured_value=result.final_state_hash[:16],
            duration_ms=0.0,
            detail=f"State hash: {result.final_state_hash[:16]}...",
        )

    def _eval_token_pipeline(self) -> CapabilityResult:
        """Evaluate token pipeline (R16)."""
        library = load_default_scenarios()
        gov = BudgetGovernor(1_000_000, 1_000_000, 1_000_000)
        pipeline = TokenPipeline(library, gov)
        results = pipeline.process_batch(library.scenario_ids)
        zero_token = sum(1 for r in results if r.zero_token)
        rate = zero_token / len(results) if results else 0.0
        ok = rate >= 0.40
        return CapabilityResult(
            capability_id="R16",
            name="Token pipeline",
            status="PASS" if ok else "FAIL",
            measured_value=rate,
            duration_ms=0.0,
            detail=f"Zero-token rate: {rate:.2%}",
        )

    def _eval_memory(self) -> CapabilityResult:
        """Evaluate memory store (R19)."""
        store = MemoryStore()
        store.write(
            record_id="eval-rec-001",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-test",
            correlation_id="corr-eval-001",
            schema_id="schema.eval@1",
            payload_hash=hashlib.sha256(b"eval").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
        )
        record = store.read("eval-rec-001", "tenant-test", 0)
        ok = record is not None
        return CapabilityResult(
            capability_id="R19",
            name="Memory store",
            status="PASS" if ok else "FAIL",
            measured_value=len(store),
            duration_ms=0.0,
            detail=f"Store has {len(store)} records",
        )

    def _eval_tenant_isolation(self) -> CapabilityResult:
        """Evaluate tenant isolation (N20)."""
        guard = TenantGuard()
        guard.store.write(
            record_id="eval-tenant-001",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-a",
            correlation_id="corr-tenant-001",
            schema_id="schema.eval@1",
            payload_hash=hashlib.sha256(b"ta").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
        )
        scope_b = TenantScope(tenant_id="tenant-b")
        result = guard.read("eval-tenant-001", scope_b)
        ok = result is None
        return CapabilityResult(
            capability_id="N20",
            name="Tenant isolation",
            status="PASS" if ok else "FAIL",
            measured_value=guard.cross_tenant_attempts,
            duration_ms=0.0,
            detail=f"Cross-tenant attempts: {guard.cross_tenant_attempts}",
        )

    def run(self) -> EvaluationReport:
        """Run evaluation on all implemented capabilities and return a report."""
        evaluators: list[Callable[[], CapabilityResult]] = [
            self._eval_schema_validation,
            self._eval_policy_gateway,
            self._eval_budget_governor,
            self._eval_simulation,
            self._eval_token_pipeline,
            self._eval_memory,
            self._eval_tenant_isolation,
        ]

        results: list[CapabilityResult] = []
        for evaluator in evaluators:
            start = time.perf_counter()
            try:
                result = evaluator()
                duration = (time.perf_counter() - start) * 1000.0
                results.append(
                    CapabilityResult(
                        capability_id=result.capability_id,
                        name=result.name,
                        status=result.status,
                        measured_value=result.measured_value,
                        duration_ms=duration,
                        detail=result.detail,
                    )
                )
            except Exception as exc:
                duration = (time.perf_counter() - start) * 1000.0
                results.append(
                    CapabilityResult(
                        capability_id="UNKNOWN",
                        name=evaluator.__name__,
                        status="FAIL",
                        measured_value=str(exc),
                        duration_ms=duration,
                        detail=f"Exception: {exc}",
                    )
                )

        report = EvaluationReport(results=results)
        report.total = len(results)
        report.passed = sum(1 for r in results if r.status == "PASS")
        report.failed = sum(1 for r in results if r.status == "FAIL")
        report.not_run = sum(1 for r in results if r.status == "NOT_RUN")
        return report
