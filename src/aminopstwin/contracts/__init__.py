"""Shared contracts: envelopes, schemas, reason codes, Clock, IdFactory.

This package is the deterministic core shared by the pre-filter (tokens) and the
Policy Gateway (gateway). It must have zero LLM-library and zero network imports.
"""

from aminopstwin.contracts.data_contract import (
    CONTRACT_V1_FIELDS,
    CONTRACT_V2_FIELDS,
    CONTRACT_V2_OPTIONAL_FIELDS,
    COUNT_FIELDS,
    PATIENT_LEVEL_FIELDS,
    REQUIRED_FIELDS,
    AggregateRecordV1,
    AggregateRecordV2,
    DataContractError,
    DataContractVersion,
    DataReaderV1,
    DataReaderV2,
    is_backward_compatible,
    validate_record,
    validate_record_v1,
    validate_record_v2,
)
from aminopstwin.contracts.idempotency import (
    IdempotencyError,
    IdempotencyResult,
    IdempotencyStatus,
    IdempotencyStore,
    InMemoryIdempotencyStore,
)
from aminopstwin.contracts.request_context import RequestContext

__all__ = [
    "DataContractError",
    "DataContractVersion",
    "AggregateRecordV1",
    "AggregateRecordV2",
    "CONTRACT_V1_FIELDS",
    "CONTRACT_V2_FIELDS",
    "CONTRACT_V2_OPTIONAL_FIELDS",
    "COUNT_FIELDS",
    "REQUIRED_FIELDS",
    "PATIENT_LEVEL_FIELDS",
    "validate_record",
    "validate_record_v1",
    "validate_record_v2",
    "is_backward_compatible",
    "DataReaderV1",
    "DataReaderV2",
    "IdempotencyError",
    "IdempotencyResult",
    "IdempotencyStatus",
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "RequestContext",
]
