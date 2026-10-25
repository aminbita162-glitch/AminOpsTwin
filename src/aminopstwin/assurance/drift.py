"""Drift detection for state-hash and denial-rate observability (P18, G18.5).

A :class:`DriftDetector` records integer-timestamped observations of (a) the
canonical state hash of the twin and (b) allow/denial events from the Policy
Gateway, and emits :class:`DriftAlert` objects when a metric crosses its
configured threshold.

Two drift signals are tracked:

* **State-hash drift** — when the recorded state hash changes between
  consecutive observations (beyond ``state_hash_threshold``; a threshold of
  ``0.0`` means any change counts as drift).
* **Denial-rate drift** — when the running denial rate
  (``denials / (denials + allows)``) exceeds ``denial_rate_threshold``.

Deterministic core: this module never calls ``datetime.now()``,
``uuid.uuid4``, ``random.*`` or ``secrets.*``. All timestamps are integers
supplied by the caller, and alert IDs are derived deterministically from the
metric name and the current observation count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

__all__ = [
    "DriftMetric",
    "DriftAlert",
    "DriftDetector",
]

#: Severity strings.
_SEVERITY_WARNING: Final[str] = "WARNING"
_SEVERITY_CRITICAL: Final[str] = "CRITICAL"

#: Denial rate at/above which severity escalates to CRITICAL.
_CRITICAL_DENIAL_RATE: Final[float] = 0.8

#: Metric names used in metrics/alerts.
_METRIC_STATE_HASH: Final[str] = "state_hash_drift"
_METRIC_DENIAL_RATE: Final[str] = "denial_rate_drift"


@dataclass(frozen=True)
class DriftMetric:
    """A single drift metric observation with its threshold status.

    Attributes
    ----------
    name:
        Metric name.
    current_value:
        Current value of the metric (float or int).
    threshold:
        Configured threshold for this metric.
    exceeded:
        True if the current value has crossed (exceeded) the threshold.
    """

    name: str
    current_value: float | int
    threshold: float | int
    exceeded: bool


@dataclass(frozen=True)
class DriftAlert:
    """An alert emitted when a drift metric crosses its threshold.

    Attributes
    ----------
    alert_id:
        Deterministic identifier for the alert.
    timestamp:
        Integer timestamp (caller-supplied, not ``datetime.now``).
    metric_name:
        Name of the metric that fired.
    current_value:
        Current value of the metric at the time of the alert.
    threshold:
        Threshold that was crossed.
    severity:
        ``"WARNING"`` or ``"CRITICAL"``.
    message:
        Human-readable description of the alert.
    """

    alert_id: str
    timestamp: int
    metric_name: str
    current_value: float | int
    threshold: float | int
    severity: str
    message: str


@dataclass
class DriftDetector:
    """Detects drift in state hashes and denial rates.

    All timestamps are integers supplied by the caller. The detector does
    not access the system clock, UUIDs, or randomness.
    """

    state_hash_threshold: float = 0.0
    denial_rate_threshold: float = 0.5

    _state_hashes: list[tuple[int, str]] = field(default_factory=list)
    _denials: list[tuple[int, str]] = field(default_factory=list)
    _allows: list[int] = field(default_factory=list)
    _alert_seq: int = 0

    # --- recording -------------------------------------------------

    def record_state_hash(self, timestamp: int, state_hash: str) -> None:
        """Record a state-hash observation at *timestamp*."""
        self._state_hashes.append((timestamp, state_hash))

    def record_denial(self, timestamp: int, reason_code: str) -> None:
        """Record a denial event at *timestamp* with *reason_code*."""
        self._denials.append((timestamp, reason_code))

    def record_allow(self, timestamp: int) -> None:
        """Record an allow event at *timestamp*."""
        self._allows.append(timestamp)

    # --- counts ----------------------------------------------------

    @property
    def total_requests(self) -> int:
        """Total requests = total denials + total allows."""
        return self.total_denials + self.total_allows

    @property
    def total_denials(self) -> int:
        """Total number of recorded denials."""
        return len(self._denials)

    @property
    def total_allows(self) -> int:
        """Total number of recorded allows."""
        return len(self._allows)

    # --- computations ----------------------------------------------

    def compute_denial_rate(self) -> float:
        """Return the running denial rate.

        Computed as ``total_denials / total_requests`` where
        ``total_requests = denials + allows``. Returns ``0.0`` when there
        are no recorded requests.
        """
        total = self.total_requests
        if total == 0:
            return 0.0
        return self.total_denials / total

    def state_hash_stable(self) -> bool:
        """Return True if all recorded state hashes are identical.

        Zero or one observations are considered stable.
        """
        hashes = {h for _, h in self._state_hashes}
        return len(hashes) <= 1

    def check_state_hash_drift(self) -> bool:
        """Return True if the state hash drifted between consecutive observations.

        Drift is detected when the latest two recorded hashes differ. The
        ``state_hash_threshold`` is not currently used to scale the change
        (hashes are opaque strings); a threshold of ``0.0`` means *any*
        change counts as drift, which is the default. A non-zero threshold is
        reserved for future per-field delta computation and is accepted but
        does not change the boolean outcome for opaque hashes.
        """
        if len(self._state_hashes) < 2:
            return False
        _, prev = self._state_hashes[-2]
        _, curr = self._state_hashes[-1]
        return prev != curr

    def check_denial_rate_drift(self) -> bool:
        """Return True if the current denial rate exceeds its threshold."""
        return self.compute_denial_rate() > self.denial_rate_threshold

    # --- metrics & alerts ------------------------------------------

    def get_metrics(self) -> list[DriftMetric]:
        """Return current metrics with their threshold status."""
        denial_rate = self.compute_denial_rate()
        return [
            DriftMetric(
                name=_METRIC_STATE_HASH,
                current_value=1 if self.check_state_hash_drift() else 0,
                threshold=self.state_hash_threshold,
                exceeded=self.check_state_hash_drift(),
            ),
            DriftMetric(
                name=_METRIC_DENIAL_RATE,
                current_value=denial_rate,
                threshold=self.denial_rate_threshold,
                exceeded=self.check_denial_rate_drift(),
            ),
        ]

    def _next_alert_id(self) -> str:
        """Return a deterministic alert id derived from the metric + sequence."""
        self._alert_seq += 1
        return f"drift-alert-{self._alert_seq:04d}"

    def _current_timestamp(self) -> int:
        """Return the latest recorded observation timestamp, or 0."""
        candidates: list[int] = []
        if self._state_hashes:
            candidates.append(self._state_hashes[-1][0])
        if self._denials:
            candidates.append(self._denials[-1][0])
        if self._allows:
            candidates.append(self._allows[-1])
        return max(candidates) if candidates else 0

    def detect_drift(self) -> list[DriftAlert]:
        """Return a list of drift alerts for any metric that exceeds its threshold.

        Alerts are emitted for:

        * state-hash change between consecutive observations
          (severity ``WARNING``); and
        * denial rate above threshold
          (severity ``WARNING`` if < 0.8, ``CRITICAL`` if >= 0.8).
        """
        alerts: list[DriftAlert] = []
        ts = self._current_timestamp()

        if self.check_state_hash_drift():
            alerts.append(
                DriftAlert(
                    alert_id=self._next_alert_id(),
                    timestamp=ts,
                    metric_name=_METRIC_STATE_HASH,
                    current_value=1,
                    threshold=self.state_hash_threshold,
                    severity=_SEVERITY_WARNING,
                    message="State hash changed between consecutive observations",
                )
            )

        denial_rate = self.compute_denial_rate()
        if self.check_denial_rate_drift():
            severity = (
                _SEVERITY_CRITICAL
                if denial_rate >= _CRITICAL_DENIAL_RATE
                else _SEVERITY_WARNING
            )
            alerts.append(
                DriftAlert(
                    alert_id=self._next_alert_id(),
                    timestamp=ts,
                    metric_name=_METRIC_DENIAL_RATE,
                    current_value=denial_rate,
                    threshold=self.denial_rate_threshold,
                    severity=severity,
                    message=(
                        f"Denial rate {denial_rate:.3f} exceeds "
                        f"threshold {self.denial_rate_threshold:.3f}"
                    ),
                )
            )

        return alerts
