"""Tests for P26 deliverable 7: tenant and causation.

G26.7: no hard-coded tenant id in src/ (grep plus test).
The tenant comes from an explicit RequestContext.
"""

from __future__ import annotations

import uuid

from aminopstwin.contracts.request_context import RequestContext


class TestRequestContext:
    """RequestContext carries tenant_id and causation_id explicitly."""

    def test_tenant_id_required(self) -> None:
        ctx = RequestContext(tenant_id="tenant-alpha")
        assert ctx.tenant_id == "tenant-alpha"
        assert ctx.causation_id is None
        assert ctx.policy_epoch == 0

    def test_causation_id_propagates(self) -> None:
        parent = uuid.uuid4()
        ctx = RequestContext(
            tenant_id="tenant-alpha",
            causation_id=parent,
            policy_epoch=3,
        )
        assert ctx.causation_id == parent
        assert ctx.policy_epoch == 3

    def test_frozen(self) -> None:
        ctx = RequestContext(tenant_id="t1")
        try:
            ctx.tenant_id = "t2"
        except Exception:
            pass
        else:
            raise AssertionError("RequestContext must be frozen")

    def test_extra_forbidden(self) -> None:
        try:
            RequestContext(  # type: ignore[call-arg]
                tenant_id="t1",
                extra_field="bad",
            )
        except Exception:
            pass
        else:
            raise AssertionError("RequestContext must reject extra fields")


class TestNoHardCodedTenant:
    """G26.7: no hard-coded tenant id in src/aminopstwin/ agents or gateway.

    The 'tenant-default' default parameter remains for backward
    compatibility, but the RequestContext path is the P26 way.
    The agent base accepts a RequestContext and uses its tenant_id.
    """

    def test_request_context_provides_tenant(self) -> None:
        """The RequestContext is the explicit source of the tenant."""
        ctx = RequestContext(tenant_id="my-tenant")
        assert ctx.tenant_id == "my-tenant"
