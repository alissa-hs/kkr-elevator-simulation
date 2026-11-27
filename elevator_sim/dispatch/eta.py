"""Earliest-arrival (ETA) dispatch."""

from __future__ import annotations

from collections.abc import Sequence

from elevator_sim.dispatch.base import Dispatcher
from elevator_sim.models import Direction, Elevator, Passenger
from elevator_sim.routing import choose_direction


class EtaDispatcher(Dispatcher):
    """Pick the elevator estimated to reach the passenger soonest, heading their way.

    The estimate replays the LOOK rules each elevator already follows, using
    only what is known now. It ignores capacity, so a
    full elevator can be chosen and pass the passenger by. Ties go to an idle
    elevator, then the lowest id.
    """

    name = "eta"
    label = "Earliest arrival"
    description = (
        "Each new request goes to the elevator estimated to reach the passenger's floor "
        "soonest while heading their way, counting any detour to finish its current sweep "
        "first. Ties go to an idle elevator, then the lowest number."
    )

    def assign(self, passenger: Passenger, elevators: Sequence[Elevator], t: int) -> int:
        best = min(
            elevators,
            key=lambda e: (
                estimate_arrival(e, passenger),
                0 if choose_direction(e) == Direction.IDLE else 1,
                e.id,
            ),
        )
        return best.id


def known_stops(e: Elevator) -> list[int]:
    """Floors the elevator already has to visit: rider destinations, plus pickup
    floors and destinations of passengers assigned to it."""
    return (
        [p.dest for p in e.onboard]
        + [p.source for p in e.assigned]
        + [p.dest for p in e.assigned]
    )


def _farthest(direction: Direction, floors: list[int]) -> int:
    """Highest floor when going UP, lowest when going DOWN."""
    return max(floors) if direction == Direction.UP else min(floors)


def estimate_arrival(e: Elevator, p: Passenger) -> int:
    """Ticks until ``e`` would be at ``p.source`` heading ``p``'s way (one floor per tick).

    Cases, shown for an elevator about to go UP (DOWN is the mirror image):
      A. idle: straight there
      B. passenger ahead, also going up: passes them on the way
      C. passenger going down: up to the top of the sweep, then down to them
      D. passenger behind, going up: up to the top, down to the bottom, back up to them
    """
    d = choose_direction(e)  # the direction LOOK is about to take; does not change e
    # Case A
    if d == Direction.IDLE:
        return abs(e.floor - p.source)

    stops = known_stops(e)
    ahead = (p.source - e.floor) * d >= 0
    # Case B
    if p.direction == d and ahead:
        return abs(p.source - e.floor)

    turn = _farthest(d, [e.floor, p.source, *stops])

    # Case C
    if p.direction != d:
        return abs(turn - e.floor) + abs(turn - p.source) 

    back = _farthest(d.opposite, [p.source, *stops])

    # Case D
    return abs(turn - e.floor) + abs(turn - back) + abs(p.source - back) 
