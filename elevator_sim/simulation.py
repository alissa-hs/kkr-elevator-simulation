"""The tick-by-tick simulation loop."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from elevator_sim.config import SimConfig
from elevator_sim.dispatch import Dispatcher, get_dispatcher
from elevator_sim.errors import SimulationError
from elevator_sim.invariants import check_invariants
from elevator_sim.io import validate_requests
from elevator_sim.models import Elevator, Passenger, PassengerState, Request
from elevator_sim.routing import move, service_floor
from elevator_sim.stream import RequestStream

START_FLOOR = 1
"""Assumption that every car starts at the ground floor."""


@dataclass
class ElevatorStats:
    """Per-car counters. Every tick counts as exactly one of moving or idle,
    so ``moving_ticks + idle_ticks == final_time + 1``."""

    elevator_id: int
    served: int = 0
    """Passengers dropped off by this car."""
    moving_ticks: int = 0
    """Ticks where the car's direction after service is not IDLE (it moves that tick)."""
    idle_ticks: int = 0
    """Ticks where the car's direction after service is IDLE."""
    stops: int = 0
    """Ticks where at least one passenger boarded or got off."""
    peak_load: int = 0
    """Highest number of riders onboard after boarding."""


@dataclass
class SimulationResult:
    """Everything a finished run produced."""

    config: SimConfig
    positions: list[tuple[int, list[int]]]
    """(t, [floor of elevator 0, 1, ...]) for every t in 0..final_time."""
    passengers: list[Passenger]
    """Every passenger, oldest first (by sort_key)."""
    final_time: int
    """Last logged tick: the first tick where everyone was delivered."""
    scheduler_name: str
    """Name of the dispatcher actually used (``dispatcher.name``).

    This takes precedence over ``config.scheduler``: when a dispatcher is
    passed to Simulation, ``config.scheduler`` is ignored and may differ.
    """
    elevator_stats: list[ElevatorStats]
    """One per elevator; index = elevator id."""


class Simulation:
    """Runs requests through the building one tick at a time.

    If ``dispatcher`` is given it is used and ``config.scheduler`` is ignored;
    otherwise the dispatcher comes from the registry by ``config.scheduler``.
    """

    def __init__(
        self,
        config: SimConfig,
        requests: Iterable[Request],
        dispatcher: Dispatcher | None = None,
    ) -> None:
        requests = list(requests)
        validate_requests(requests, config)
        self.config = config
        self.elevators = [
            Elevator(id=i, floor=START_FLOOR, capacity=config.capacity)
            for i in range(config.num_elevators)
        ]
        self.stream = RequestStream(requests)
        self.dispatcher = dispatcher if dispatcher is not None else get_dispatcher(
            config.scheduler, config
        )
        self.passengers: list[Passenger] = []
        self.stats = [ElevatorStats(elevator_id=e.id) for e in self.elevators]
        self._has_run = False

    def run(self) -> SimulationResult:
        """Run to completion. Can only be called once per Simulation."""
        if self._has_run:
            raise SimulationError("run() can only be called once per Simulation")
        self._has_run = True

        config = self.config
        positions: list[tuple[int, list[int]]] = []
        starvation_limit = 2 * config.num_floors * (self.stream.total + 1)
        t = 0
        while True:
            self._release(t)
            self._service(t)
            positions.append((t, [e.floor for e in self.elevators]))
            if config.check_invariants:
                check_invariants(t, self.elevators, self.passengers, config)
            if self.stream.exhausted and all(
                p.state is PassengerState.DELIVERED for p in self.passengers
            ):
                return SimulationResult(
                    config=config,
                    positions=positions,
                    passengers=sorted(self.passengers, key=lambda p: p.sort_key),
                    final_time=t,
                    scheduler_name=self.dispatcher.name,
                    elevator_stats=self.stats,
                )
            self._check_guards(t, starvation_limit)
            for e in self.elevators:
                e.prev_floor = e.floor
                move(e, config.num_floors)
            t += 1

    def _release(self, t: int) -> None:
        """Turn requests due at ``t`` into passengers and assign each to a car."""
        for request in self.stream.pop_until(t):
            passenger = Passenger.from_request(request)
            car_id = self.dispatcher.assign(passenger, tuple(self.elevators), t)
            if (
                not isinstance(car_id, int)
                or isinstance(car_id, bool)
                or not 0 <= car_id < len(self.elevators)
            ):
                raise SimulationError(
                    f"dispatcher '{self.dispatcher.name}' returned invalid elevator id "
                    f"{car_id!r} for passenger '{passenger.id}' at tick {t}; "
                    f"expected 0..{len(self.elevators) - 1}"
                )
            passenger.assigned_elevator = car_id
            self.elevators[car_id].assigned.append(passenger)
            self.passengers.append(passenger)

    def _service(self, t: int) -> None:
        """Unload, choose direction and board for each car, then update its stats."""
        for e, stats in zip(self.elevators, self.stats):
            result = service_floor(e, t)
            stats.served += result.dropped_off
            if result.dropped_off or result.picked_up:
                stats.stops += 1
            stats.peak_load = max(stats.peak_load, e.load)
            if e.is_idle:
                stats.idle_ticks += 1
            else:
                stats.moving_ticks += 1

    def _check_guards(self, t: int, starvation_limit: int) -> None:
        """Stop runaway runs: starvation always, max_ticks when set."""
        for p in self.passengers:
            if p.state is not PassengerState.DELIVERED and t - p.request_time > starvation_limit:
                raise SimulationError(
                    f"tick {t}: passenger '{p.id}' has waited {t - p.request_time} ticks, "
                    f"over the starvation limit of {starvation_limit}"
                )
        if self.config.max_ticks is not None and t == self.config.max_ticks:
            undelivered = sum(p.state is not PassengerState.DELIVERED for p in self.passengers)
            raise SimulationError(
                f"reached max_ticks={self.config.max_ticks} with {undelivered} passenger(s) "
                f"undelivered"
                + ("" if self.stream.exhausted else " and requests still to come")
            )
