"""Summary statistics for a finished run."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from elevator_sim.simulation import ElevatorStats, SimulationResult


@dataclass(frozen=True)
class Stats:
    """min, max, mean, median and p95 of one measure. All None when there are no values."""

    min: int | None = None
    max: int | None = None
    mean: float | None = None
    median: float | None = None
    p95: int | None = None


def percentile(sorted_values: Sequence[int], p: int) -> int:
    """Nearest-rank percentile: the value at position ceil(p/100 * n), counting from 1.

    Always returns a value from the data. ``sorted_values`` must be sorted and non-empty, and ``0 < p <= 100``.
    """
    rank = math.ceil(p * len(sorted_values) / 100)
    return sorted_values[rank - 1]


def compute_stats(values: Sequence[int]) -> Stats:
    if not values:
        return Stats()
    ordered = sorted(values)
    return Stats(
        min=ordered[0],
        max=ordered[-1],
        mean=statistics.fmean(ordered),
        median=statistics.median(ordered),
        p95=percentile(ordered, 95),
    )


@dataclass(frozen=True)
class Summary:
    passenger_count: int
    final_time: int
    scheduler_name: str
    wait: Stats
    travel: Stats
    total: Stats
    elevators: tuple[ElevatorStats, ...]
    max_wait_passenger_id: str | None
    """Passenger with the longest wait; ties go to the earliest request. None if no passengers."""


def compute_summary(result: SimulationResult) -> Summary:
    """Build the summary for a finished run. Does not modify ``result``."""
    passengers = result.passengers
    longest = min(passengers, key=lambda p: (-p.wait_time, p.sort_key), default=None)
    return Summary(
        passenger_count=len(passengers),
        final_time=result.final_time,
        scheduler_name=result.scheduler_name,
        wait=compute_stats([p.wait_time for p in passengers]),
        travel=compute_stats([p.travel_time for p in passengers]),
        total=compute_stats([p.total_time for p in passengers]),
        elevators=tuple(result.elevator_stats),
        max_wait_passenger_id=longest.id if longest else None,
    )
