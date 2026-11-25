"""Run configuration."""

from __future__ import annotations

from dataclasses import dataclass

from elevator_sim.dispatch import DISPATCHERS, unknown_scheduler_message
from elevator_sim.errors import ConfigError


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


REQUIRED_FIELDS = ("num_floors", "num_elevators", "capacity")


@dataclass(frozen=True)
class SimConfig:
    """Settings fixed for the whole run. Validated on creation.

    The building fields (num_floors, num_elevators, capacity) are the three
    settings. They have no defaults: they must always be configured. A missing one can be
    reported as a ConfigError.
    """

    num_floors: int | None = None
    num_elevators: int | None = None
    capacity: int | None = None
    scheduler: str = "nearest"
    check_invariants: bool = False
    """Run the consistency checks after every tick. Used by tests; not a CLI option."""

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise ConfigError listing every invalid field."""
        missing = [name for name in REQUIRED_FIELDS if getattr(self, name) is None]
        if missing:
            raise ConfigError(f"missing required setting(s): {', '.join(missing)}")

        errors: list[str] = []

        def check_min(name: str, minimum: int) -> None:
            value = getattr(self, name)
            if not _is_int(value):
                errors.append(f"{name} must be an integer, got {value!r}")
            elif value < minimum:
                errors.append(f"{name} must be >= {minimum}, got {value}")

        check_min("num_floors", 2)
        check_min("num_elevators", 1)
        check_min("capacity", 1)

        if self.scheduler not in DISPATCHERS:
            errors.append(unknown_scheduler_message(self.scheduler))

        if errors:
            raise ConfigError("; ".join(errors))
