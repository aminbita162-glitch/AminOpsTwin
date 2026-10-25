"""Enterprise hardening package (P8, §4.5, §29, T10).

Tenant isolation, evaluation harness, export manifest verification,
transparency contract, load smoke, and API fuzzing support.
"""

from aminopstwin.enterprise.evaluation import (
    CapabilityResult,
    EvaluationHarness,
    EvaluationReport,
)
from aminopstwin.enterprise.isolation import (
    IsolationResult,
    TenantIsolationSuite,
    run_isolation_suite,
)
from aminopstwin.enterprise.load_smoke import (
    LoadSmokeResult,
    run_load_smoke,
)
from aminopstwin.enterprise.manifest import (
    ExportManifest,
    ManifestEntry,
    ManifestError,
    build_manifest,
)
from aminopstwin.enterprise.rls import (
    RLSEngine,
    RLSPolicy,
    generate_executor_rls_policies,
)
from aminopstwin.enterprise.tenant import (
    TenantAccessError,
    TenantGuard,
    TenantScope,
)
from aminopstwin.enterprise.transparency import (
    TransparencyError,
    TransparencyResponse,
    build_transparency_response,
)

__all__ = [
    # tenant isolation
    "TenantGuard",
    "TenantAccessError",
    "TenantScope",
    # isolation suite (P18, G18.1)
    "TenantIsolationSuite",
    "IsolationResult",
    "run_isolation_suite",
    # RLS (P18, G18.3)
    "RLSPolicy",
    "RLSEngine",
    "generate_executor_rls_policies",
    # evaluation harness
    "CapabilityResult",
    "EvaluationHarness",
    "EvaluationReport",
    # export manifest
    "ExportManifest",
    "ManifestEntry",
    "ManifestError",
    "build_manifest",
    # transparency
    "TransparencyResponse",
    "TransparencyError",
    "build_transparency_response",
    # load smoke
    "LoadSmokeResult",
    "run_load_smoke",
]
