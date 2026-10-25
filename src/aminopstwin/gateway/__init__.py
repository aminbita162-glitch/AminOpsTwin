"""Gateway package — Policy Gateway (S1).

This package has ZERO LLM-library imports and ZERO network imports (import-linter,
§G1.7). The Gateway is a pure function that evaluates policy independently of any
LLM or agent suggestion. It cannot be bypassed (§S1, §3.2). It is deny-by-default.
"""

from aminopstwin.gateway.quota import (
    QuotaAwareGateway,
    TenantQuotaEngine,
)

__all__ = [
    "QuotaAwareGateway",
    "TenantQuotaEngine",
]
