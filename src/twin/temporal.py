"""Temporal state model for the digital twin (P3).

Tracks the evolution of operational state over time. Each time step
produces a new immutable OperationalSnapshot. The model is deterministic:
the same seed and inputs produce the same sequence of snapshots and
state hashes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from src.contracts.canonical import canonical_hash
from src.twin.entities import (
    Arrival,
    OperationalSnapshot,
    Queue,
    Resource,
    ServiceCompletion,
    Site,
)

__all__ = [
    "TemporalState",
    "snapshot_hash",
]


def snapshot_hash(snapshot: OperationalSnapshot) -> str:
    """Return the SHA-256 hash of the canonical bytes of a snapshot."""
    return canonical_hash(snapshot.to_canonical_dict())


class TemporalState:
    """Temporal state model — sequence of immutable snapshots.

    The state advances in discrete time steps. Each step produces a new
    :class:`OperationalSnapshot`. The full history of snapshots is
    retained for replay (G3.1).

    Determinism: given the same seed, same inputs, and same
    sequence of events, the state hash sequence is identical.
    """

    def __init__(
        self,
        *,
        seed: int = 0,
        initial_sites: dict[str, Site] | None = None,
        initial_resources: dict[str, Resource] | None = None,
        initial_queues: dict[str, Queue] | None = None,
    ) -> None:
        self._seed: int = seed
        self._tick: int = 0
        self._sites: dict[str, Site] = dict(initial_sites or {})
        self._resources: dict[str, Resource] = dict(
            initial_resources or {}
        )
        self._queues: dict[str, Queue] = dict(initial_queues or {})
        self._arrivals: list[Arrival] = []
        self._completions: list[ServiceCompletion] = []
        self._snapshots: list[OperationalSnapshot] = []
        self._snapshot_hashes: list[str] = []
        self._arrival_counter: int = 0
        self._completion_counter: int = 0

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def sites(self) -> dict[str, Site]:
        return dict(self._sites)

    @property
    def resources(self) -> dict[str, Resource]:
        return dict(self._resources)

    @property
    def queues(self) -> dict[str, Queue]:
        return dict(self._queues)

    def get_snapshot(self) -> OperationalSnapshot:
        """Return the current state as an immutable snapshot."""
        return OperationalSnapshot(
            timestamp=self._tick,
            sites=dict(self._sites),
            resources=dict(self._resources),
            queues=dict(self._queues),
            arrivals=list(self._arrivals),
            completions=list(self._completions),
        )

    def add_arrival(
        self,
        site_id: str,
        queue_id: str,
        arrival_time: int,
        service_time: int,
    ) -> Arrival:
        """Add a new arrival to the state."""
        self._arrival_counter += 1
        arrival = Arrival(
            arrival_id=f"arr-{self._arrival_counter:08d}",
            site_id=site_id,
            queue_id=queue_id,
            arrival_time=arrival_time,
            service_time=service_time,
        )
        self._arrivals.append(arrival)
        # Update queue's current_length and total_arrivals
        q = self._queues.get(queue_id)
        if q is not None:
            new_len = min(q.current_length + 1, q.capacity)
            self._queues[queue_id] = Queue(
                queue_id=q.queue_id,
                site_id=q.site_id,
                name=q.name,
                current_length=new_len,
                total_arrivals=q.total_arrivals + 1,
                total_completions=q.total_completions,
                capacity=q.capacity,
            )
        return arrival

    def add_completion(
        self,
        site_id: str,
        queue_id: str,
        arrival_id: str,
        start_time: int,
        completion_time: int,
    ) -> ServiceCompletion:
        """Add a new service completion event."""
        self._completion_counter += 1
        wait_time = max(0, start_time - 0)  # simplified
        completion = ServiceCompletion(
            completion_id=f"comp-{self._completion_counter:08d}",
            site_id=site_id,
            queue_id=queue_id,
            arrival_id=arrival_id,
            start_time=start_time,
            completion_time=completion_time,
            wait_time=wait_time,
        )
        self._completions.append(completion)
        # Update queue: decrement current_length, increment completions
        q = self._queues.get(queue_id)
        if q is not None:
            self._queues[queue_id] = Queue(
                queue_id=q.queue_id,
                site_id=q.site_id,
                name=q.name,
                current_length=max(0, q.current_length - 1),
                total_arrivals=q.total_arrivals,
                total_completions=q.total_completions + 1,
                capacity=q.capacity,
            )
        return completion

    def add_site(self, site: Site) -> None:
        self._sites[site.site_id] = site

    def add_resource(self, resource: Resource) -> None:
        self._resources[resource.resource_id] = resource

    def add_queue(self, queue: Queue) -> None:
        self._queues[queue.queue_id] = queue

    def advance(self) -> OperationalSnapshot:
        """Advance one time step and return the new snapshot."""
        self._tick += 1
        snap = self.get_snapshot()
        self._snapshots.append(snap)
        h = snapshot_hash(snap)
        self._snapshot_hashes.append(h)
        return snap

    def checkpoint(self) -> str:
        """Return the state hash of the current snapshot (for replay)."""
        return snapshot_hash(self.get_snapshot())

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    @property
    def snapshot_hashes(self) -> list[str]:
        return list(self._snapshot_hashes)

    def final_hash(self) -> str:
        """Return the state hash of the latest snapshot."""
        return snapshot_hash(self.get_snapshot())

    def save_state(self) -> bytes:
        """Serialise the full temporal state to deterministic bytes."""
        data: dict[str, Any] = {
            "seed": self._seed,
            "tick": self._tick,
            "sites": {
                k: v.model_dump()
                for k, v in sorted(self._sites.items())
            },
            "resources": {
                k: v.model_dump()
                for k, v in sorted(self._resources.items())
            },
            "queues": {
                k: v.model_dump()
                for k, v in sorted(self._queues.items())
            },
            "arrivals": [a.model_dump() for a in self._arrivals],
            "completions": [
                c.model_dump() for c in self._completions
            ],
            "arrival_counter": self._arrival_counter,
            "completion_counter": self._completion_counter,
        }
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    def restore_state(self, data: bytes) -> None:
        """Restore full temporal state from deterministic bytes."""
        raw = json.loads(data.decode("utf-8"))
        self._seed = raw["seed"]
        self._tick = raw["tick"]
        self._sites = {
            k: Site(**v) for k, v in raw["sites"].items()
        }
        self._resources = {
            k: Resource(**v) for k, v in raw["resources"].items()
        }
        self._queues = {
            k: Queue(**v) for k, v in raw["queues"].items()
        }
        self._arrivals = [Arrival(**a) for a in raw["arrivals"]]
        self._completions = [
            ServiceCompletion(**c) for c in raw["completions"]
        ]
        self._arrival_counter = raw["arrival_counter"]
        self._completion_counter = raw["completion_counter"]
        self._snapshots = []
        self._snapshot_hashes = []

    def state_hash(self) -> str:
        """Return the SHA-256 hash of the full serialised state."""
        return hashlib.sha256(self.save_state()).hexdigest()
