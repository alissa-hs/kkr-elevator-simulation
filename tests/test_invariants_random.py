"""Randomized and stress runs with every invariant checked on every tick.

Each seed builds its own random building and request list with
random.Random(seed), so any failure can be reproduced from its seed.
"""

import random

import pytest

from elevator_sim.config import SimConfig
from elevator_sim.models import PassengerState, Request
from elevator_sim.simulation import Simulation

SEEDS = range(200)


def random_scenario(seed):
    """Return (settings, requests) for one random run."""
    rng = random.Random(seed)
    num_floors = rng.randint(2, 30)
    settings = {
        "num_floors": num_floors,
        "num_elevators": rng.randint(1, 5),
        "capacity": rng.randint(1, 8),
    }
    requests = []
    for i in range(rng.randint(0, 60)):
        source = rng.randint(1, num_floors)
        dest = rng.choice([f for f in range(1, num_floors + 1) if f != source])
        requests.append(Request(rng.randint(0, 100), f"p{i}", source, dest, input_order=i))
    return settings, requests


def run(settings, requests):
    config = SimConfig(**settings, check_invariants=True)
    return Simulation(config, requests).run()


def passenger_rows(result):
    return [
        (p.id, p.assigned_elevator, p.pickup_time, p.dropoff_time) for p in result.passengers
    ]


def check_run(result, settings, requests):
    """Everything that must hold for any finished run."""
    # Everyone delivered, nobody lost or invented.
    assert sorted(p.id for p in result.passengers) == sorted(r.passenger_id for r in requests)
    assert all(p.state is PassengerState.DELIVERED for p in result.passengers)

    # No car beats one floor per tick; nobody is picked up before asking.
    for p in result.passengers:
        assert p.travel_time >= abs(p.dest - p.source), p.id
        assert p.wait_time >= 0, p.id

    # One position row per tick, no gaps, every car inside the building.
    assert [t for t, _ in result.positions] == list(range(result.final_time + 1))
    for _, row in result.positions:
        assert len(row) == settings["num_elevators"]
        assert all(1 <= floor <= settings["num_floors"] for floor in row)

    # Per-car stats add up.
    for stats in result.elevator_stats:
        assert stats.moving_ticks + stats.idle_ticks == result.final_time + 1
    assert sum(s.served for s in result.elevator_stats) == len(requests)


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"seed={s}")
def test_random_run_satisfies_all_checks(seed):
    settings, requests = random_scenario(seed)
    result = run(settings, requests)
    check_run(result, settings, requests)

    # Determinism: the same scenario again gives identical results.
    again = run(*random_scenario(seed))
    assert again.positions == result.positions
    assert passenger_rows(again) == passenger_rows(result)
    assert again.elevator_stats == result.elevator_stats


def test_burst_at_one_floor_with_capacity_one():
    """Longest possible queue: one car carrying 60 people one at a time to the top."""
    settings = {"num_floors": 30, "num_elevators": 1, "capacity": 1}
    requests = [Request(0, f"p{i}", 1, 30, input_order=i) for i in range(60)]
    result = run(settings, requests)
    check_run(result, settings, requests)

    # Oldest first: each round trip takes 58 ticks, so passenger i waits 58 * i.
    waits = [p.wait_time for p in result.passengers]
    assert waits == [58 * i for i in range(60)]
    starvation_limit = 2 * 30 * (60 + 1)
    assert max(waits) < starvation_limit


def test_everyone_going_opposite_ways_from_one_floor():
    settings = {"num_floors": 20, "num_elevators": 2, "capacity": 3}
    rng = random.Random(0)
    requests = [
        Request(rng.randint(0, 20), f"p{i}", 10, rng.randint(11, 20) if i % 2 else rng.randint(1, 9),
                input_order=i)
        for i in range(40)
    ]
    result = run(settings, requests)
    check_run(result, settings, requests)


def test_two_floor_building():
    settings = {"num_floors": 2, "num_elevators": 3, "capacity": 2}
    rng = random.Random(1)
    requests = [
        Request(rng.randint(0, 30), f"p{i}", 1 + i % 2, 2 - i % 2, input_order=i)
        for i in range(40)
    ]
    result = run(settings, requests)
    check_run(result, settings, requests)
    for p in result.passengers:
        assert p.travel_time == 1
