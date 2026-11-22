"""Per-tick consistency checks, run when ``SimConfig.check_invariants`` is on."""

from __future__ import annotations

from collections.abc import Sequence

from elevator_sim.config import SimConfig
from elevator_sim.errors import SimulationError
from elevator_sim.models import Direction, Elevator, Passenger, PassengerState

EXPECTED_STATE = {
    "assigned": PassengerState.WAITING,
    "onboard": PassengerState.RIDING,
}


def check_invariants(
    t: int,
    elevators: Sequence[Elevator],
    passengers: Sequence[Passenger],
    config: SimConfig,
) -> None:
    """Raise SimulationError naming the tick, car and rule for the first broken rule.

    Runs after service, before cars move. ``passengers`` is every passenger
    released so far.
    """

    def fail(rule: int, message: str, elevator: int | None = None) -> None:
        where = f"tick {t}" + (f", elevator {elevator}" if elevator is not None else "")
        raise SimulationError(f"{where}, rule {rule}: {message}")

    for e in elevators:
        # 1. Inside the building, at most one floor per tick.
        if not 1 <= e.floor <= config.num_floors:
            fail(1, f"floor {e.floor} is outside 1..{config.num_floors}", e.id)
        if abs(e.floor - e.prev_floor) > 1:
            fail(1, f"moved from floor {e.prev_floor} to {e.floor} in one tick", e.id)
        # 2. Capacity.
        if e.load > e.capacity:
            fail(2, f"{e.load} riders exceed capacity {e.capacity}", e.id)
        # 8. An idle car is empty.
        if e.direction == Direction.IDLE and e.onboard:
            fail(8, f"idle with {e.load} rider(s) onboard", e.id)
        # 7. Every rider's destination is strictly ahead.
        for p in e.onboard:
            if (p.dest - e.floor) * e.direction <= 0:
                fail(7, f"rider '{p.id}' going to floor {p.dest} is not ahead of floor "
                        f"{e.floor} going {e.direction.name}", e.id)

    # Where each passenger is, keyed by object identity.
    places: dict[int, list[tuple[str, int]]] = {}
    for e in elevators:
        for list_name in ("assigned", "onboard"):
            for p in getattr(e, list_name):
                places.setdefault(id(p), []).append((list_name, e.id))

    released = {id(p) for p in passengers}
    for e in elevators:
        for p in e.assigned + e.onboard:
            if id(p) not in released:
                fail(3, f"passenger '{p.id}' is in a car but was never released", e.id)

    for p in passengers:
        found = places.get(id(p), [])
        car = found[0][1] if found else None
        # 3. Exactly one place: one car's assigned, one car's onboard, or delivered.
        if len(found) > 1:
            fail(3, f"passenger '{p.id}' is in {len(found)} places: {found}", car)
        if not found and p.state is not PassengerState.DELIVERED:
            fail(3, f"passenger '{p.id}' is in no car but is {p.state.name}")
        # 4. Only in the assigned car's lists.
        if found and car != p.assigned_elevator:
            fail(4, f"passenger '{p.id}' is assigned to elevator {p.assigned_elevator}", car)
        # 5. State matches the place.
        expected = EXPECTED_STATE[found[0][0]] if found else PassengerState.DELIVERED
        if p.state is not expected:
            fail(5, f"passenger '{p.id}' is {p.state.name}, expected {expected.name}", car)
        # 6. Times are consistent.
        if p.pickup_time is not None and p.pickup_time < p.request_time:
            fail(6, f"passenger '{p.id}' picked up at {p.pickup_time} before request at "
                    f"{p.request_time}", car)
        if p.dropoff_time is not None and (
            p.pickup_time is None or p.dropoff_time <= p.pickup_time
        ):
            fail(6, f"passenger '{p.id}' dropped off at {p.dropoff_time}, not after pickup "
                    f"at {p.pickup_time}", car)
