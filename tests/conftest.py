"""Shared test helpers.

Imports of simulation modules are done inside the helpers so this file loads
even while the package is being built up step by step.
"""

from __future__ import annotations

import itertools
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _reset_input_order() -> None:
    """Give every test a fresh input_order counter for req()."""
    global _order
    _order = itertools.count()


_order = itertools.count()


# Building used by tests unless a test says otherwise.
# These are test conveniences only; SimConfig itself has no defaults for them.
TEST_BUILDING = {"num_floors": 10, "num_elevators": 1, "capacity": 8, "start_floor": 1}


def make_config(**overrides: Any):
    """Build a SimConfig on TEST_BUILDING with invariant checks on."""
    from elevator_sim.config import SimConfig

    settings = {**TEST_BUILDING, "check_invariants": True, **overrides}
    return SimConfig(**settings)


def req(time: int, passenger_id: str, source: int, dest: int):
    """Build a Request with an auto-incrementing input_order."""
    from elevator_sim.models import Request

    return Request(
        time=time,
        passenger_id=passenger_id,
        source=source,
        dest=dest,
        input_order=next(_order),
    )


def run_sim(requests: list, dispatcher=None, **config: Any):
    """Run a simulation with invariants checked.

    Returns (result, passengers_by_id).
    """
    from elevator_sim.simulation import Simulation

    result = Simulation(make_config(**config), requests, dispatcher=dispatcher).run()
    return result, {p.id: p for p in result.passengers}
