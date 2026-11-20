"""Run configuration."""

from __future__ import annotations

from dataclasses import dataclass


class ConfigError(ValueError):
    """Invalid simulation configuration."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


REQUIRED_FIELDS = ("num_floors", "num_elevators", "capacity", "start_floor")


@dataclass(frozen=True)
class SimConfig:
    """Settings fixed for the whole run. Validated on creation.

    The building fields (num_floors, num_elevators, capacity, start_floor) have
    no defaults: they must always be configured. They are typed ``int | None``
    only so a missing one can be reported as a ConfigError; after validation
    they are always ints.
    """

    num_floors: int | None = None
    num_elevators: int | None = None
    capacity: int | None = None
    start_floor: int | None = None
    scheduler: str = "nearest"
    output_dir: str = "output"
    max_ticks: int | None = None
    """Largest allowed final_time (inclusive). None = no global cap."""
    check_invariants: bool = False

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Raise ConfigError listing every invalid field."""
        # Imported here: dispatch imports ConfigError from this module.
        from elevator_sim.dispatch import DISPATCHERS, unknown_scheduler_message

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

        if not _is_int(self.start_floor):
            errors.append(f"start_floor must be an integer, got {self.start_floor!r}")
        elif _is_int(self.num_floors) and not 1 <= self.start_floor <= self.num_floors:
            errors.append(
                f"start_floor must be between 1 and num_floors ({self.num_floors}), "
                f"got {self.start_floor}"
            )

        if self.scheduler not in DISPATCHERS:
            errors.append(unknown_scheduler_message(self.scheduler))

        if self.max_ticks is not None:
            check_min("max_ticks", 1)

        if errors:
            raise ConfigError("; ".join(errors))
