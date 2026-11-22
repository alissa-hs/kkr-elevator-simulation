"""Input validation (and, from step 9, CSV loading and output writers)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from elevator_sim.config import SimConfig
from elevator_sim.errors import InputError
from elevator_sim.models import Request


def validate_requests(requests: Sequence[Request], config: SimConfig) -> None:
    """Check every request against the row rules and the building's floor range.

    Called by ``Simulation.__init__``, so requests built in code get the same
    checks as CSV input. Raises one InputError listing every problem, one per
    line, each starting with ``line <n>:`` or ``request '<id>':``. If any floor
    is too high, a final line gives the fix using the highest bad floor.
    """
    problems: list[str] = []
    id_counts = Counter(r.passenger_id for r in requests)
    highest_bad_floor: int | None = None

    for r in requests:
        if r.time < 0:
            problems.append(f"{r.label}: time {r.time} is negative")
        if r.source == r.dest:
            problems.append(f"{r.label}: source and dest are both floor {r.source}")
        if id_counts[r.passenger_id] > 1:
            problems.append(f"{r.label}: duplicate id '{r.passenger_id}'")
        for floor in dict.fromkeys((r.source, r.dest)):  # each distinct floor once, in order
            if floor < 1:
                problems.append(f"{r.label}: floor {floor} is below 1")
            elif floor > config.num_floors:
                problems.append(f"{r.label}: floor {floor} is above --floors {config.num_floors}")
                highest_bad_floor = max(floor, highest_bad_floor or floor)

    if highest_bad_floor is not None:
        problems.append(f"use --floors {highest_bad_floor} or higher")
    if problems:
        raise InputError("\n".join(problems))
