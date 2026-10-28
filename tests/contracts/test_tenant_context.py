"""Tests for P26 deliverable 7: tenant and causation.

G26.7: no hard-coded tenant id in src/ (grep plus test).
The tenant comes from an explicit RequestContext.
"""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path

import pytest
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
        with pytest.raises(Exception):  # noqa: B017
            ctx.tenant_id = "t2"  # type: ignore[misc]

    def test_extra_forbidden(self) -> None:
        with pytest.raises(Exception):  # noqa: B017
            RequestContext(  # type: ignore[call-arg]
                tenant_id="t1",
                extra_field="bad",
            )

    def test_missing_tenant_rejected(self) -> None:
        """RequestContext without tenant_id must be rejected."""
        with pytest.raises(Exception):  # noqa: B017
            RequestContext()  # type: ignore[call-arg]


class TestNoHardCodedTenant:
    """G26.7: no hard-coded tenant id in src/aminopstwin/.

    The literal string "tenant-default" must not appear anywhere
    in src/. The tenant must come from an explicit RequestContext.
    """

    @staticmethod
    def _src_root() -> Path:
        return Path(__file__).resolve().parent.parent.parent / "src"

    def test_no_tenant_default_in_src(self) -> None:
        """Grep src/ for 'tenant-default' and fail if any match is found."""
        src = self._src_root()
        result = subprocess.run(
            ["git", "grep", "-n", "tenant-default", "--", "src/"],
            cwd=src.parent,
            capture_output=True,
            text=True,
        )
        # git grep exits 0 if matches found, 1 if no matches
        assert result.returncode == 1, (
            f"Found 'tenant-default' in src/:\n{result.stdout}"
        )

    def test_request_context_provides_tenant(self) -> None:
        """The RequestContext is the explicit source of the tenant."""
        ctx = RequestContext(tenant_id="my-tenant")
        assert ctx.tenant_id == "my-tenant"
