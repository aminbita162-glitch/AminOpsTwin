"""P9 integration package — signed exports, cross-component integration,
deployment preparation, and backup/restore drill (§38, §25, §26)."""

from aminopstwin.integration.backup import (
    BACKUP_RPO_MINUTES,
    BACKUP_RTO_HOURS,
    BackupDrill,
    BackupError,
    BackupResult,
)
from aminopstwin.integration.deployment import (
    CLEAN_ROOM_STEPS,
    DEPLOYMENT_CONFIG,
    RPO_MINUTES,
    RTO_HOURS,
    CleanRoomInstall,
    CleanRoomStep,
    OfflineDemoConfig,
    RenderDeploymentConfig,
    get_clean_room_steps,
)
from aminopstwin.integration.exports import (
    NO_AGENT_HELD_KEY,
    ExportBundle,
    ExportSignatureError,
    ExportSignatureStatus,
    build_export_bundle,
    sign_bundle,
    verify_bundle,
)
from aminopstwin.integration.integration import (
    IntegrationHarness,
    IntegrationReport,
    IntegrationTestResult,
)

__all__ = [
    # exports
    "ExportBundle",
    "ExportSignatureError",
    "ExportSignatureStatus",
    "build_export_bundle",
    "sign_bundle",
    "verify_bundle",
    "NO_AGENT_HELD_KEY",
    # integration
    "IntegrationHarness",
    "IntegrationReport",
    "IntegrationTestResult",
    # deployment
    "CleanRoomInstall",
    "CleanRoomStep",
    "CLEAN_ROOM_STEPS",
    "OfflineDemoConfig",
    "RenderDeploymentConfig",
    "DEPLOYMENT_CONFIG",
    "RPO_MINUTES",
    "RTO_HOURS",
    "get_clean_room_steps",
    # backup
    "BackupDrill",
    "BackupError",
    "BackupResult",
    "BACKUP_RPO_MINUTES",
    "BACKUP_RTO_HOURS",
]
