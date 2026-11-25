"""Discrete-time elevator simulation: LOOK routing with pluggable dispatchers.

Run from Python with ``simulate()``, or from the command line with
``python -m elevator_sim --input requests.csv --floors N --elevators N --capacity N``.
"""

from __future__ import annotations

from collections.abc import Iterable

from elevator_sim.config import SimConfig
from elevator_sim.errors import InputError
from elevator_sim.io import load_requests_csv
from elevator_sim.metrics import compute_summary
from elevator_sim.models import Request
from elevator_sim.output import write_outputs
from elevator_sim.simulation import Simulation, SimulationResult

__version__ = "0.1.0"

__all__ = [
    "Request",
    "SimConfig",
    "SimulationResult",
    "compute_summary",
    "load_requests_csv",
    "simulate",
    "write_outputs",
]


def simulate(
    requests: Iterable[Request | tuple],
    num_floors: int | None = None,
    num_elevators: int | None = None,
    capacity: int | None = None,
    dispatcher: str = "nearest",
) -> SimulationResult:
    """Run a simulation and return the result.

    ``requests`` holds ``Request`` objects or ``(time, id, source, dest)`` tuples;
    a tuple's position in the list is its ``input_order``. ``num_floors``,
    ``num_elevators`` and ``capacity`` are required; leaving one out raises
    ConfigError. ``dispatcher`` is the name of a built-in dispatcher, the same
    choices as the CLI's ``--dispatcher``. Call ``write_outputs(result)`` to save the CSV files.
    """
    config = SimConfig(
        num_floors=num_floors, num_elevators=num_elevators, capacity=capacity,
        dispatcher=dispatcher,
    )
    return Simulation(config, _to_requests(requests)).run()


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _to_requests(items: Iterable[Request | tuple]) -> list[Request]:
    """Turn tuples into Requests, listing every malformed item in one InputError."""
    requests: list[Request] = []
    problems: list[str] = []
    for position, item in enumerate(items):
        if isinstance(item, Request):
            requests.append(item)
            continue
        if not isinstance(item, (tuple, list)) or len(item) != 4:
            problems.append(
                f"request at position {position}: expected (time, id, source, dest), got {item!r}"
            )
            continue
        time, pid, source, dest = item
        if not isinstance(pid, str) or not pid:
            problems.append(
                f"request at position {position}: id must be a non-empty string, got {pid!r}"
            )
            continue
        bad = [
            f"request '{pid}': {name} must be a whole number, got {value!r}"
            for name, value in (("time", time), ("source", source), ("dest", dest))
            if not _is_int(value)
        ]
        if bad:
            problems.extend(bad)
            continue
        requests.append(Request(time, pid, source, dest, input_order=position))
    if problems:
        raise InputError("\n".join(problems))
    return requests
