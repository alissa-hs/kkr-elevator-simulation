"""Dispatcher interface: picks one elevator per passenger at request time."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from elevator_sim.config import SimConfig
    from elevator_sim.models import Elevator, Passenger


class Dispatcher(ABC):
    """Base class for dispatch strategies.

    ``assign`` must be read-only: it may inspect the elevators and the
    passenger but must not change them. The simulation appends the passenger
    to the chosen car. A dispatcher never sees future requests.
    """

    name: ClassVar[str]
    label: ClassVar[str] = ""
    """Human-readable name for reports, e.g. "Nearest elevator"."""
    description: ClassVar[str] = ""
    """One sentence on how this dispatcher chooses, for reports."""

    def __init__(self, config: SimConfig) -> None:
        self.config = config

    @abstractmethod
    def assign(self, passenger: Passenger, elevators: Sequence[Elevator], t: int) -> int:
        """Return the id of the elevator this passenger is assigned to."""
