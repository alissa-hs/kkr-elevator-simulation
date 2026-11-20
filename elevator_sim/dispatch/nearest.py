"""Nearest-car dispatch."""

from __future__ import annotations

from collections.abc import Sequence

from elevator_sim.dispatch.base import Dispatcher
from elevator_sim.models import Direction, Elevator, Passenger


class NearestCarDispatcher(Dispatcher):
    """Pick the car closest to the passenger's floor.

    Ties go to idle cars, then the lowest id. Direction of travel, load and
    capacity are deliberately ignored.
    """

    name = "nearest"

    def assign(self, passenger: Passenger, elevators: Sequence[Elevator], t: int) -> int:
        best = min(
            elevators,
            key=lambda e: (
                abs(e.floor - passenger.source),
                0 if e.direction == Direction.IDLE else 1,
                e.id,
            ),
        )
        return best.id
