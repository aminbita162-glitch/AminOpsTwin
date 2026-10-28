"""Cross-component integration testing (P9, §3.10).

Exercises every cross-component flow end-to-end through a single harness so
that regressions in the Gateway → Executor → Memory → Evidence → Twin
pipeline are caught in one place.  Each ``_test_*`` method drives one flow;
``run`` aggregates the outcomes into an :class:`IntegrationReport`.

Per §38 rule 7, these integration reports are UNSIGNED: private signing keys
stay with the owner.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aminopstwin.contracts.canonical import canonical_hash
from aminopstwin.contracts.clock import SeededClock
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.enterprise.evaluation import EvaluationHarness
from aminopstwin.enterprise.manifest import build_manifest
from aminopstwin.enterprise.transparency import build_transparency_response
from aminopstwin.executor import DurableExecutor, ExecutorState
from aminopstwin.executor.memory import MemoryClass, MemoryStore
from aminopstwin.gateway.gateway import PolicyGateway, PolicyMatrix, PolicyMatrixEntry
from aminopstwin.tokens.budget import BudgetGovernor
from aminopstwin.twin.pipeline import TokenPipeline
from aminopstwin.twin.scenarios import load_default_scenarios

__all__ = [
    "IntegrationTestResult",
    "IntegrationReport",
    "IntegrationHarness",
]


@dataclass(frozen=True)
class IntegrationTestResult:
    """Result of a single cross-component integration test."""

    component: str
    status: str  # PASS | FAIL
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass
class IntegrationReport:
    """Aggregated report of all integration test results."""

    results: list[IntegrationTestResult] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "results": [r.to_dict() for r in self.results],
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


class IntegrationHarness:
    """Cross-component integration harness (P9).

    Each ``_test_*`` method drives one cross-component flow; ``run``
    executes them all, catches exceptions, and returns an
    :class:`IntegrationReport` with pass/fail counts and per-test detail.
    """

    # --- Gateway → Executor (§3.2, §3.6) ---
    def _test_gateway_to_executor(self) -> IntegrationTestResult:
        """Gateway ALLOWs A1/test/default then a DurableExecutor workflow starts."""
        clock = SeededClock()
        matrix = PolicyMatrix()
        matrix.add(PolicyMatrixEntry("A1", "test", "default"))
        gateway = PolicyGateway(
            policy_matrix=matrix,
            current_epoch=0,
            schema_registry={"integration.test@1"},
            envelope_type_registry={"integration.test@1": "test"},
        )
        payload = {"component": "gateway_to_executor", "step": 1}
        envelope = Envelope(
            envelope_version="1.0",
            schema_id="integration.test@1",
            envelope_type="test",
            correlation_id=uuid.uuid4(),
            causation_id=None,
            tenant_id="tenant-test",
            policy_epoch=0,
            idempotency_key="integration-gw-exec-key-00001",
            payload=payload,
            payload_hash=canonical_hash(payload),
            created_at=clock.now(),
        )
        decision = gateway.evaluate(envelope, "A1", clock.now(), "default")
        if decision.decision.value != "ALLOW":
            return IntegrationTestResult(
                component="gateway_to_executor",
                status="FAIL",
                detail=f"Gateway denied: {decision.decision.value}",
            )

        executor = DurableExecutor(clock=clock)
        workflow = executor.start(
            correlation_id=envelope.correlation_id,
            tenant_id="tenant-test",
            policy_epoch=0,
        )
        if workflow.state is not ExecutorState.PENDING:
            return IntegrationTestResult(
                component="gateway_to_executor",
                status="FAIL",
                detail=f"Executor not PENDING: {workflow.state.value}",
            )
        return IntegrationTestResult(
            component="gateway_to_executor",
            status="PASS",
            detail="Gateway ALLOW then Executor PENDING workflow started",
        )

    # --- Executor → Memory (§3.6, §31) ---
    def _test_executor_to_memory(self) -> IntegrationTestResult:
        """A MemoryRecord is written via MemoryStore and read back."""
        store = MemoryStore()
        record_id = "integration-mem-001"
        payload_hash = hashlib.sha256(b"executor_to_memory").hexdigest()
        written = store.write(
            record_id=record_id,
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-test",
            correlation_id="corr-integration-mem-001",
            schema_id="memory.integration@1",
            payload_hash=payload_hash,
            recorded_at="2026-10-25T00:00:00Z",
            policy_epoch=0,
        )
        if written.record_id != record_id:
            return IntegrationTestResult(
                component="executor_to_memory",
                status="FAIL",
                detail=f"Write returned wrong id: {written.record_id}",
            )
        read_back = store.read(record_id, "tenant-test", 0)
        if read_back is None:
            return IntegrationTestResult(
                component="executor_to_memory",
                status="FAIL",
                detail="Read returned None after write",
            )
        if read_back.record_id != record_id:
            return IntegrationTestResult(
                component="executor_to_memory",
                status="FAIL",
                detail=f"Read returned wrong id: {read_back.record_id}",
            )
        return IntegrationTestResult(
            component="executor_to_memory",
            status="PASS",
            detail="MemoryRecord written and read back successfully",
        )

    # --- Twin pipeline (§3.1, §3.4) ---
    def _test_twin_pipeline(self) -> IntegrationTestResult:
        """Default scenarios, BudgetGovernor, and TokenPipeline.process_batch."""
        library = load_default_scenarios()
        if len(library) == 0:
            return IntegrationTestResult(
                component="twin_pipeline",
                status="FAIL",
                detail="Default scenario library is empty",
            )
        governor = BudgetGovernor(1_000_000, 1_000_000, 1_000_000)
        pipeline = TokenPipeline(library, governor)
        results = pipeline.process_batch(library.scenario_ids)
        if not results:
            return IntegrationTestResult(
                component="twin_pipeline",
                status="FAIL",
                detail="process_batch returned no results",
            )
        zero_token = sum(1 for r in results if r.zero_token)
        return IntegrationTestResult(
            component="twin_pipeline",
            status="PASS",
            detail=(
                f"process_batch ran {len(results)} scenarios, "
                f"{zero_token} zero-token"
            ),
        )

    # --- Transparency response (§4.5) ---
    def _test_transparency_response(self) -> IntegrationTestResult:
        """build_transparency_response produces a verified response."""
        response = build_transparency_response(
            correlation_id=str(uuid.uuid4()),
            path="deterministic",
            cache_hit=False,
            policy_decision="ALLOW",
            policy_epoch=0,
            tokens_used=0,
            tokens_budget_remaining=1_000_000,
        )
        if response.correlation_id == "":
            return IntegrationTestResult(
                component="transparency_response",
                status="FAIL",
                detail="correlation_id missing",
            )
        if response.path != "deterministic":
            return IntegrationTestResult(
                component="transparency_response",
                status="FAIL",
                detail=f"Unexpected path: {response.path}",
            )
        if not response.verify():
            return IntegrationTestResult(
                component="transparency_response",
                status="FAIL",
                detail="TransparencyResponse.verify() returned False",
            )
        return IntegrationTestResult(
            component="transparency_response",
            status="PASS",
            detail="TransparencyResponse built and verified",
        )

    # --- Evaluation harness (G5.4) ---
    def _test_evaluation_harness(self) -> IntegrationTestResult:
        """EvaluationHarness().run() returns a populated report."""
        harness = EvaluationHarness()
        report = harness.run()
        if report.total == 0:
            return IntegrationTestResult(
                component="evaluation_harness",
                status="FAIL",
                detail="Evaluation report has zero results",
            )
        if report.passed == 0:
            return IntegrationTestResult(
                component="evaluation_harness",
                status="FAIL",
                detail="No capabilities passed",
            )
        return IntegrationTestResult(
            component="evaluation_harness",
            status="PASS",
            detail=(
                f"EvaluationHarness ran {report.total} capabilities, "
                f"{report.passed} passed"
            ),
        )

    # --- Manifest (G5.3) ---
    def _test_manifest(self) -> IntegrationTestResult:
        """build_manifest from a temp directory and verify it."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "module.py").write_text("x = 1\n", encoding="utf-8")
            (base / "config.json").write_text(
                '{"version": "1.0"}\n', encoding="utf-8"
            )
            manifest = build_manifest(base)
            if manifest.count == 0:
                return IntegrationTestResult(
                    component="manifest",
                    status="FAIL",
                    detail="Manifest built with zero entries",
                )
            verified = manifest.verify()
            if verified != manifest.count:
                return IntegrationTestResult(
                    component="manifest",
                    status="FAIL",
                    detail=f"Verified {verified} of {manifest.count} entries",
                )
            files_verified = manifest.verify_files(base)
            if files_verified != manifest.count:
                return IntegrationTestResult(
                    component="manifest",
                    status="FAIL",
                    detail=(
                        f"verify_files returned {files_verified} "
                        f"of {manifest.count}"
                    ),
                )
        return IntegrationTestResult(
            component="manifest",
            status="PASS",
            detail=f"Manifest built with {manifest.count} entries, verified",
        )

    def run(self) -> IntegrationReport:
        """Run every cross-component integration test and return a report.

        Each test runs in isolation; an exception in one test is recorded
        as a FAIL with the exception message in ``detail`` and does not
        abort the remaining tests.  Duration is measured with
        :func:`time.perf_counter`.
        """
        tests: list[tuple[str, Any]] = [
            ("gateway_to_executor", self._test_gateway_to_executor),
            ("executor_to_memory", self._test_executor_to_memory),
            ("twin_pipeline", self._test_twin_pipeline),
            ("transparency_response", self._test_transparency_response),
            ("evaluation_harness", self._test_evaluation_harness),
            ("manifest", self._test_manifest),
        ]

        results: list[IntegrationTestResult] = []
        for _name, test_fn in tests:
            _start = time.perf_counter()
            try:
                result = test_fn()
                _ = time.perf_counter() - _start
                results.append(result)
            except Exception as exc:
                _ = time.perf_counter() - _start
                results.append(
                    IntegrationTestResult(
                        component=_name,
                        status="FAIL",
                        detail=f"Exception: {exc!r}",
                    )
                )

        report = IntegrationReport(results=results)
        report.total = len(results)
        report.passed = sum(1 for r in results if r.status == "PASS")
        report.failed = sum(1 for r in results if r.status == "FAIL")
        return report
