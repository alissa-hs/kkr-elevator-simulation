import copy

import pytest
from conftest import make_config

from elevator_sim.config import ConfigError
from elevator_sim.dispatch import Dispatcher, get_dispatcher
from elevator_sim.dispatch.nearest import NearestCarDispatcher
from elevator_sim.models import Direction, Elevator, Passenger


def passenger(source, dest=None, pid="p"):
    if dest is None:
        dest = source + 1 if source < 10 else source - 1
    return Passenger(id=pid, request_time=0, source=source, dest=dest, input_order=0)


def car(id, floor, direction=Direction.IDLE, capacity=8):
    return Elevator(id=id, floor=floor, capacity=capacity, direction=direction)


@pytest.fixture
def nearest():
    return NearestCarDispatcher(make_config(num_elevators=3))


def test_picks_the_closest_car(nearest):
    cars = [car(0, 1), car(1, 5), car(2, 9)]
    assert nearest.assign(passenger(6), cars, t=0) == 1


def test_idle_car_wins_a_distance_tie(nearest):
    cars = [car(0, 3, Direction.UP), car(1, 7)]
    assert nearest.assign(passenger(5), cars, t=0) == 1


def test_lowest_id_wins_when_everything_ties(nearest):
    cars = [car(0, 1), car(1, 1)]
    assert nearest.assign(passenger(4), cars, t=0) == 0


def test_lowest_id_wins_a_tie_between_moving_cars(nearest):
    cars = [car(0, 3, Direction.UP), car(1, 7, Direction.DOWN)]
    assert nearest.assign(passenger(5), cars, t=0) == 0


def test_ignores_direction_of_travel(nearest):
    # Car 0 is heading away from floor 5, but it is still the closest.
    cars = [car(0, 4, Direction.DOWN), car(1, 9)]
    assert nearest.assign(passenger(5), cars, t=0) == 0


def test_ignores_capacity(nearest):
    full = car(0, 5, Direction.UP, capacity=1)
    full.onboard.append(passenger(4, 9, pid="rider"))
    assert full.is_full
    cars = [full, car(1, 8)]
    assert nearest.assign(passenger(5), cars, t=0) == 0


def test_single_elevator_always_gets_the_passenger(nearest):
    cars = [car(0, 3)]
    for source in (1, 3, 7, 10):
        assert nearest.assign(passenger(source), cars, t=0) == 0


def test_choice_does_not_depend_on_list_order(nearest):
    tie_on_distance = [car(0, 3, Direction.UP), car(1, 7)]
    full_tie = [car(0, 1), car(1, 1)]
    for cars in (tie_on_distance, full_tie):
        p = passenger(5)
        assert nearest.assign(p, cars, t=0) == nearest.assign(p, list(reversed(cars)), t=0)


def test_assign_does_not_change_any_elevator_or_passenger(nearest):
    busy = car(0, 4, Direction.UP)
    busy.onboard.append(passenger(2, 8, pid="rider"))
    busy.assigned.append(passenger(6, 1, pid="waiting"))
    cars = [busy, car(1, 9), car(2, 1, Direction.DOWN)]
    p = passenger(5, pid="new")
    cars_before, p_before = copy.deepcopy(cars), copy.deepcopy(p)

    nearest.assign(p, cars, t=3)

    assert cars == cars_before
    assert p == p_before


def test_get_dispatcher_returns_registered_strategy():
    config = make_config()
    dispatcher = get_dispatcher("nearest", config)
    assert isinstance(dispatcher, NearestCarDispatcher)
    assert dispatcher.config is config
    assert dispatcher.name == "nearest"


def test_get_dispatcher_rejects_unknown_name():
    with pytest.raises(ConfigError, match=r"unknown scheduler 'x'; choose from: nearest"):
        get_dispatcher("x", make_config())


def test_dispatcher_without_assign_cannot_be_created():
    class Forgetful(Dispatcher):
        name = "forgetful"

    with pytest.raises(TypeError):
        Forgetful(make_config())
