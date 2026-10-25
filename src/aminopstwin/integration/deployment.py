"""Deployment preparation: clean-room install steps, offline demo, and Render config.

Implements the §25 clean-room verification sequence (11 steps), the offline demo
configuration (§26 readiness), and the Render deployment configuration for the
AminOpsTwin project. Per §38 rule 7, export preparation produces UNSIGNED reports;
private signing keys stay with the owner.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CleanRoomStep:
    """A single step in the clean-room verification sequence (§25)."""

    step_number: int
    name: str
    command: str
    expected: str


CLEAN_ROOM_STEPS: list[CleanRoomStep] = [
    CleanRoomStep(
        step_number=1,
        name="Start fresh container",
        command="docker run --rm -it aminopstwin/cleanroom:latest /bin/bash",
        expected="Fresh container started with no prior state",
    ),
    CleanRoomStep(
        step_number=2,
        name="Clone at tag",
        command="git clone --branch v{release} --depth 1 https://example.invalid/aminopstwin.git",
        expected="Repository checked out at the specified release tag",
    ),
    CleanRoomStep(
        step_number=3,
        name="Verify manifest",
        command="python -m src.evidence.verify_manifest",
        expected="Manifest hash matches the release attestation",
    ),
    CleanRoomStep(
        step_number=4,
        name="Create venv and install",
        command="python3.12 -m venv .venv && .venv/bin/pip install -e .",
        expected="Virtual environment created and project installed",
    ),
    CleanRoomStep(
        step_number=5,
        name="Disable network",
        command="docker network disconnect bridge $HOSTNAME",
        expected="Container has no outbound network access",
    ),
    CleanRoomStep(
        step_number=6,
        name="Run migrations",
        command=".venv/bin/alembic upgrade head",
        expected="All migrations applied successfully",
    ),
    CleanRoomStep(
        step_number=7,
        name="Generate synthetic data",
        command=".venv/bin/python -m src.fixtures_gen.generate --seed 42",
        expected="Synthetic dataset generated with deterministic seed",
    ),
    CleanRoomStep(
        step_number=8,
        name="Run smoke suite offline",
        command=".venv/bin/python -m pytest -m smoke --no-network",
        expected="All smoke tests pass with network disabled",
    ),
    CleanRoomStep(
        step_number=9,
        name="Assert zero outbound connections",
        command=".venv/bin/python -m src.assurance.assert_no_outbound",
        expected="Zero outbound network connections observed",
    ),
    CleanRoomStep(
        step_number=10,
        name="Compare state hash",
        command=".venv/bin/python -m src.evidence.compare_state_hash",
        expected="State hash matches the golden reference",
    ),
    CleanRoomStep(
        step_number=11,
        name="Write report",
        command=".venv/bin/python -m src.evidence.write_cleanroom_report",
        expected="Unsigned clean-room report written (§38 rule 7)",
    ),
]


@dataclass(frozen=True)
class CleanRoomInstall:
    """A clean-room installation comprising the §25 verification sequence."""

    steps: list[CleanRoomStep] = field(default_factory=lambda: list(CLEAN_ROOM_STEPS))

    @property
    def step_count(self) -> int:
        """Return the number of steps in this clean-room install."""
        return len(self.steps)


@dataclass(frozen=True)
class OfflineDemoConfig:
    """Configuration for an offline demonstration (§26 readiness)."""

    network_disabled: bool = True
    seed: int = 42
    scenario_count: int = 5
    duration_seconds: float = 30.0


@dataclass(frozen=True)
class RenderDeploymentConfig:
    """Configuration for deploying AminOpsTwin to Render.com."""

    service_name: str = "aminopstwin-web"
    runtime: str = "python"
    plan: str = "starter"
    env_vars: dict[str, str] = field(default_factory=dict)


# Owner defaults (configurable per §26): RPO = 30 minutes, RTO = 2 hours.
RPO_MINUTES: int = 30
RTO_HOURS: int = 2

DEPLOYMENT_CONFIG: RenderDeploymentConfig = RenderDeploymentConfig(
    service_name="aminopstwin-web",
)


def get_clean_room_steps() -> list[CleanRoomStep]:
    """Return the clean-room verification steps (§25)."""
    return list(CLEAN_ROOM_STEPS)
