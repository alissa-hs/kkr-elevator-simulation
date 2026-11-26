"""LOOK routing: how each car moves once it has passengers.

All LOOK logic lives here. The dispatcher only picks which car serves a
passenger; it never touches these rules.

Each tick the simulation calls ``service_floor`` for every car (unload, choose
direction, board), and later ``move``.
"""

from __future__ import annotations

from dataclasses import dataclass

from elevator_sim.errors import SimulationError
from elevator_sim.models import Direction, Elevator, PassengerState

ROUTING_NAME = "LOOK"
ROUTING_DESCRIPTION = (
    "Each elevator keeps moving in its current direction while it has stops ahead, "
    "picks up passengers going the same way, and reverses only when nothing is left ahead."
)


@dataclass(frozen=True)
class ServiceResult:
    """What happened at a car's floor during one ``service_floor`` call."""

    dropped_off: int
    picked_up: int


def choose_direction(e: Elevator) -> Direction:
    """Return the direction the car should take after unloading. Does not change the car.

    A moving car keeps going while there is a target ahead or someone here
    going its way, otherwise reverses if there is work behind, otherwise goes
    idle. An idle car follows the oldest passenger waiting here, or else heads
    toward the oldest assigned passenger.
    """
    here = e.waiting_here()
    d = e.direction

    if d != Direction.IDLE:
        if e.has_target_in(d) or any(p.direction == d for p in here):
            pass  # keep going
        elif e.has_target_in(d.opposite) or any(p.direction == d.opposite for p in here):
            d = d.opposite  # reverse
        else:
            d = Direction.IDLE

    if d == Direction.IDLE:
        if here:
            d = here[0].direction  # oldest passenger at this floor
        elif e.assigned:
            oldest = min(e.assigned, key=lambda p: p.sort_key)
            d = Direction.UP if oldest.source > e.floor else Direction.DOWN

    return d


def service_floor(e: Elevator, t: int) -> ServiceResult:
    """Unload, choose direction, then board, all at the car's current floor at tick ``t``."""
    # 1. Unload riders whose destination is this floor.
    leaving = [p for p in e.onboard if p.dest == e.floor]
    for p in leaving:
        p.dropoff_time = t
        p.state = PassengerState.DELIVERED
    e.onboard = [p for p in e.onboard if p.dest != e.floor]

    # 2. Choose direction.
    e.direction = choose_direction(e)

    # 3. Board passengers here going the car's way, oldest first, while there is room.
    #    An idle car matches nobody, so it boards no one.
    boarded = 0
    for p in e.waiting_here():
        if e.is_full:
            break
        if p.direction != e.direction:
            continue
        p.pickup_time = t
        p.state = PassengerState.RIDING
        e.assigned.remove(p)
        e.onboard.append(p)
        boarded += 1

    return ServiceResult(dropped_off=len(leaving), picked_up=boarded)


def move(e: Elevator, num_floors: int) -> None:
    """Move the car one floor in its direction (no-op when idle).

    Raises SimulationError if the move would leave ``1..num_floors``. Under
    correct LOOK this never happens: a car never heads past its last target.
    """
    if e.direction == Direction.IDLE:
        return
    new_floor = e.floor + e.direction
    if not 1 <= new_floor <= num_floors:
        raise SimulationError(
            f"elevator {e.id} would move from floor {e.floor} to {new_floor}, "
            f"outside 1..{num_floors}"
        )
    e.floor = new_floor
