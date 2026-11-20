"""Core data model: directions, requests, passengers and elevators."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum


class Direction(IntEnum):
    """Travel direction. The value is the floor delta per move."""

    UP = 1
    DOWN = -1
    IDLE = 0

    @property
    def opposite(self) -> Direction:
        """UP <-> DOWN; IDLE stays IDLE. (Plain ``-d`` would return an int.)"""
        return Direction(-self.value)


class PassengerState(Enum):
    WAITING = "waiting"
    RIDING = "riding"
    DELIVERED = "delivered"


@dataclass(frozen=True)
class Request:
    """One input row: passenger ``passenger_id`` asks at ``time`` to go source -> dest."""

    time: int
    passenger_id: str
    source: int
    dest: int
    input_order: int = 0
    """0-based position among data rows (blank lines skipped). Tie-break for sorting."""
    line: int | None = field(default=None, compare=False)
    """Physical file line (header = line 1); None for requests built in code."""

    @property
    def direction(self) -> Direction:
        return Direction.UP if self.dest > self.source else Direction.DOWN

    @property
    def label(self) -> str:
        """How error messages refer to this request."""
        return f"line {self.line}" if self.line is not None else f"request '{self.passenger_id}'"


@dataclass
class Passenger:
    """A released request, tracked through waiting, riding and delivery."""

    id: str
    request_time: int
    source: int
    dest: int
    input_order: int
    assigned_elevator: int | None = None
    state: PassengerState = PassengerState.WAITING
    pickup_time: int | None = None
    dropoff_time: int | None = None

    @classmethod
    def from_request(cls, request: Request) -> Passenger:
        return cls(
            id=request.passenger_id,
            request_time=request.time,
            source=request.source,
            dest=request.dest,
            input_order=request.input_order,
        )

    @property
    def direction(self) -> Direction:
        return Direction.UP if self.dest > self.source else Direction.DOWN

    @property
    def sort_key(self) -> tuple[int, int]:
        """Defines "oldest first" everywhere: (request_time, input_order)."""
        return (self.request_time, self.input_order)

    @property
    def wait_time(self) -> int | None:
        if self.dropoff_time is None or self.pickup_time is None:
            return None
        return self.pickup_time - self.request_time

    @property
    def travel_time(self) -> int | None:
        if self.dropoff_time is None or self.pickup_time is None:
            return None
        return self.dropoff_time - self.pickup_time

    @property
    def total_time(self) -> int | None:
        if self.dropoff_time is None:
            return None
        return self.dropoff_time - self.request_time


@dataclass
class Elevator:
    """One car. LOOK rules that drive it live in ``routing.py``."""

    id: int
    floor: int
    capacity: int
    direction: Direction = Direction.IDLE
    onboard: list[Passenger] = field(default_factory=list)
    assigned: list[Passenger] = field(default_factory=list)
    prev_floor: int | None = None
    """Floor at the previous tick; used only by invariant checks."""

    def __post_init__(self) -> None:
        if self.prev_floor is None:
            self.prev_floor = self.floor

    @property
    def load(self) -> int:
        return len(self.onboard)

    @property
    def is_full(self) -> bool:
        return self.load >= self.capacity

    @property
    def is_idle(self) -> bool:
        return self.direction == Direction.IDLE

    def targets(self) -> set[int]:
        """Floors this car must visit: rider destinations and pickup floors."""
        return {p.dest for p in self.onboard} | {p.source for p in self.assigned}

    def has_target_in(self, direction: Direction) -> bool:
        """True if any target is strictly above (UP) or strictly below (DOWN)."""
        if direction == Direction.UP:
            return any(f > self.floor for f in self.targets())
        if direction == Direction.DOWN:
            return any(f < self.floor for f in self.targets())
        return False

    def waiting_here(self) -> list[Passenger]:
        """Assigned passengers waiting at the current floor, oldest first."""
        return sorted(
            (p for p in self.assigned if p.source == self.floor),
            key=lambda p: p.sort_key,
        )
