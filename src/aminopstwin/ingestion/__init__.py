"""Shadow-Mode Ingestion package (Idea S3, P13, G13.4).

Data Contract v1 shadow ingestion gateway with schema enforcement,
k-min cell suppression, and hashed receipts.
"""

from aminopstwin.ingestion.shadow_gateway import (
    DATA_CONTRACT_V1_COLUMNS,
    DEFAULT_K_MIN,
    Receipt,
    ShadowGateway,
    ShadowIngestionError,
    ShadowIngestionResult,
    ShadowIngestionStatus,
)

__all__ = [
    "ShadowGateway",
    "ShadowIngestionResult",
    "ShadowIngestionStatus",
    "ShadowIngestionError",
    "Receipt",
    "DATA_CONTRACT_V1_COLUMNS",
    "DEFAULT_K_MIN",
]
