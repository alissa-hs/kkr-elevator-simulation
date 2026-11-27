import copy

import pytest
from conftest import make_config

from elevator_sim.dispatch import Dispatcher, get_dispatcher
from elevator_sim.dispatch.eta import EtaDispatcher, estimate_arrival
from elevator_sim.dispatch.nearest import NearestCarDispatcher
from elevator_sim.errors import ConfigError
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
    with pytest.raises(ConfigError, match=r"unknown dispatcher 'x'; choose from: nearest, eta$"):
        get_dispatcher("x", make_config())


def test_dispatcher_without_assign_cannot_be_created():
    class Forgetful(Dispatcher):
        name = "forgetful"

    with pytest.raises(TypeError):
        Forgetful(make_config())


# --- ETA ---------------------------------------------------------------------


@pytest.fixture
def eta():
    return EtaDispatcher(make_config(num_floors=60, num_elevators=3))


def riding(e, *dests):
    """Put riders on elevator ``e`` going to each of ``dests``."""
    for i, dest in enumerate(dests):
        e.onboard.append(passenger(e.floor, dest, pid=f"rider{i}"))
    return e


def test_eta_idle_elevator_goes_straight_there():
    assert estimate_arrival(car(0, 1), passenger(6, 9)) == 5


def test_eta_passenger_ahead_going_the_same_way_is_picked_up_in_passing():
    e = riding(car(0, 3, Direction.UP), 15)
    assert estimate_arrival(e, passenger(8, 12)) == 5


def test_eta_passenger_at_the_elevator_going_its_way_is_zero():
    e = riding(car(0, 6, Direction.UP), 15)
    assert estimate_arrival(e, passenger(6, 9)) == 0


def test_eta_opposite_direction_finishes_the_sweep_first():
    # The PDF sample at tick 10: up to 51, then back down to 20.
    e = riding(car(0, 11, Direction.UP), 51, 37)
    assert estimate_arrival(e, passenger(20, 1)) == 40 + 31


def test_eta_opposite_direction_beyond_the_sweep_turns_at_the_passenger():
    e = riding(car(0, 3, Direction.UP), 10)
    assert estimate_arrival(e, passenger(15, 2)) == 12


def test_eta_behind_same_direction_needs_a_full_loop():
    # Up to 15, down to 4 (the passenger), then they board going up.
    e = riding(car(0, 10, Direction.UP), 15)
    assert estimate_arrival(e, passenger(4, 8)) == 5 + 11 + 0


def test_eta_behind_loop_goes_down_to_the_lowest_known_stop():
    # A pickup at 2 going to 1 is already assigned, so the sweep goes down to 1 first.
    e = riding(car(0, 10, Direction.UP), 15)
    e.assigned.append(passenger(2, 1, pid="waiting"))
    assert estimate_arrival(e, passenger(4, 8)) == 5 + 14 + 3


def test_eta_uses_the_direction_the_elevator_is_about_to_take():
    # Marked UP but nothing is above it, so LOOK is about to reverse to DOWN.
    e = riding(car(0, 9, Direction.UP), 3)
    assert estimate_arrival(e, passenger(5, 1)) == 4


def test_eta_counts_work_given_earlier_in_the_same_tick():
    # Elevator 0 is idle but was just sent to floor 8 (going to 9); it will head up first.
    busy = car(0, 1)
    busy.assigned.append(passenger(8, 9, pid="first"))
    assert estimate_arrival(busy, passenger(5, 2)) == 8 + 4


def test_eta_skips_a_nearer_elevator_that_is_heading_away(eta, nearest):
    # Elevator 0 is closer (9 floors) but must reach 51 first; idle elevator 1 is 19 away.
    cars = [riding(car(0, 11, Direction.UP), 51, 37), car(1, 1)]
    p = passenger(20, 1, pid="passenger3")
    assert nearest.assign(p, cars, t=10) == 0
    assert eta.assign(p, cars, t=10) == 1


def test_eta_prefers_a_farther_elevator_that_is_free(eta):
    busy = car(0, 1)
    busy.assigned.append(passenger(8, 9, pid="first"))
    cars = [busy, car(1, 10)]
    assert eta.assign(passenger(5, 2), cars, t=0) == 1  # nearest would pick elevator 0


def test_eta_idle_elevator_wins_a_tie(eta):
    cars = [riding(car(0, 3, Direction.UP), 9), car(1, 7)]
    assert eta.assign(passenger(5, 8), cars, t=0) == 1  # both 2 ticks away


def test_eta_lowest_id_wins_when_everything_ties(eta):
    assert eta.assign(passenger(4, 8), [car(0, 1), car(1, 1)], t=0) == 0


def test_eta_ignores_capacity(eta):
    full = riding(car(0, 3, Direction.UP, capacity=1), 15)
    assert full.is_full
    assert eta.assign(passenger(5, 9), [full, car(1, 9)], t=0) == 0


def test_eta_assign_does_not_change_any_elevator_or_passenger(eta):
    busy = riding(car(0, 4, Direction.UP), 8)
    busy.assigned.append(passenger(6, 1, pid="waiting"))
    cars = [busy, car(1, 9), car(2, 1, Direction.DOWN)]
    p = passenger(5, pid="new")
    cars_before, p_before = copy.deepcopy(cars), copy.deepcopy(p)

    eta.assign(p, cars, t=3)

    assert cars == cars_before
    assert p == p_before


def test_get_dispatcher_returns_eta():
    dispatcher = get_dispatcher("eta", make_config())
    assert isinstance(dispatcher, EtaDispatcher)
    assert dispatcher.label == "Earliest arrival"
