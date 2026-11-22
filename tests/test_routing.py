import copy

import pytest

from elevator_sim.errors import SimulationError
from elevator_sim.models import Direction, Elevator, Passenger, PassengerState
from elevator_sim.routing import ServiceResult, choose_direction, move, service_floor

NUM_FLOORS = 10


def car(floor, direction=Direction.IDLE, capacity=8):
    return Elevator(id=0, floor=floor, capacity=capacity, direction=direction)


def waiting(pid, source, dest, request_time=0, input_order=0):
    """A passenger assigned to the car, not yet picked up."""
    return Passenger(id=pid, request_time=request_time, source=source, dest=dest,
                     input_order=input_order, assigned_elevator=0)


def rider(pid, source, dest, pickup_time=0):
    """A passenger already in the car."""
    p = waiting(pid, source, dest)
    p.state = PassengerState.RIDING
    p.pickup_time = pickup_time
    return p


def ids(passengers):
    return [p.id for p in passengers]


def test_idle_car_with_no_work_stays_put():
    e = car(4)
    service_floor(e, t=0)
    move(e, NUM_FLOORS)
    assert e.direction is Direction.IDLE
    assert e.floor == 4


def test_idle_car_heads_toward_its_pickup():
    e = car(1)
    e.assigned.append(waiting("a", source=4, dest=8))
    service_floor(e, t=0)
    assert e.direction is Direction.UP
    move(e, NUM_FLOORS)
    assert e.floor == 2


def test_idle_car_heads_down_to_a_pickup_below():
    e = car(7)
    e.assigned.append(waiting("a", source=3, dest=9))
    service_floor(e, t=0)
    assert e.direction is Direction.DOWN


def test_idle_car_targets_the_oldest_assignment_not_the_nearest():
    e = car(6)
    e.assigned.append(waiting("newer", source=4, dest=1, request_time=5))
    e.assigned.append(waiting("older", source=9, dest=1, request_time=2))
    service_floor(e, t=5)
    assert e.direction is Direction.UP


def test_moving_car_does_not_reverse_early():
    e = car(5, Direction.UP)
    e.onboard.append(rider("r", source=1, dest=8))
    e.assigned.append(waiting("a", source=2, dest=1))
    service_floor(e, t=4)
    assert e.direction is Direction.UP


def test_car_reverses_after_last_target_ahead():
    e = car(8, Direction.UP)
    e.onboard.append(rider("r", source=1, dest=8))
    e.assigned.append(waiting("a", source=2, dest=1))
    service_floor(e, t=7)
    assert e.direction is Direction.DOWN
    assert e.onboard == []


def test_passenger_going_the_other_way_does_not_board():
    e = car(5, Direction.UP)
    e.onboard.append(rider("r", source=1, dest=8))
    e.assigned.append(waiting("down", source=5, dest=2))
    service_floor(e, t=4)
    assert e.direction is Direction.UP
    assert ids(e.onboard) == ["r"]
    assert ids(e.assigned) == ["down"]


def test_car_turns_and_boards_at_the_turnaround_floor():
    e = car(9, Direction.UP)
    e.assigned.append(waiting("down", source=9, dest=3))
    service_floor(e, t=8)
    assert e.direction is Direction.DOWN
    assert ids(e.onboard) == ["down"]
    assert e.assigned == []


def test_full_car_boards_oldest_and_leaves_the_rest():
    e = car(1, capacity=2)
    e.assigned.extend([
        waiting("third", 1, 5, request_time=2),
        waiting("first", 1, 6, request_time=0),
        waiting("second", 1, 7, request_time=1),
    ])
    service_floor(e, t=2)
    assert ids(e.onboard) == ["first", "second"]
    assert ids(e.assigned) == ["third"]
    assert e.assigned[0].state is PassengerState.WAITING


def test_same_request_time_boards_lower_input_order_first():
    e = car(1, capacity=1)
    e.assigned.extend([
        waiting("later_row", 1, 5, request_time=3, input_order=1),
        waiting("earlier_row", 1, 5, request_time=3, input_order=0),
    ])
    service_floor(e, t=3)
    assert ids(e.onboard) == ["earlier_row"]
    assert ids(e.assigned) == ["later_row"]


def test_unload_happens_before_boarding():
    e = car(5, Direction.UP, capacity=1)
    e.onboard.append(rider("leaving", source=1, dest=5))
    e.assigned.append(waiting("joining", source=5, dest=9))
    service_floor(e, t=4)
    assert ids(e.onboard) == ["joining"]


def test_idle_car_follows_the_oldest_passenger_here():
    e = car(5)
    e.assigned.extend([
        waiting("down", 5, 1, request_time=1),
        waiting("up", 5, 9, request_time=0),
    ])
    service_floor(e, t=1)
    assert e.direction is Direction.UP
    assert ids(e.onboard) == ["up"]
    assert ids(e.assigned) == ["down"]


def test_car_goes_idle_at_top_floor_with_nothing_left():
    e = car(NUM_FLOORS, Direction.UP)
    e.onboard.append(rider("r", source=1, dest=NUM_FLOORS))
    service_floor(e, t=9)
    assert e.direction is Direction.IDLE
    move(e, NUM_FLOORS)
    assert e.floor == NUM_FLOORS


def test_unload_sets_dropoff_time_and_state():
    e = car(6, Direction.UP)
    a, b, stays = rider("a", 1, 6), rider("b", 2, 6), rider("stays", 1, 9)
    e.onboard.extend([a, b, stays])
    service_floor(e, t=5)
    for p in (a, b):
        assert p.state is PassengerState.DELIVERED
        assert p.dropoff_time == 5
    assert ids(e.onboard) == ["stays"]
    assert stays.dropoff_time is None


def test_boarding_sets_pickup_time_and_state():
    e = car(3)
    p = waiting("a", 3, 7, request_time=1)
    e.assigned.append(p)
    service_floor(e, t=2)
    assert p.state is PassengerState.RIDING
    assert p.pickup_time == 2


def test_choose_direction_does_not_change_the_car():
    e = car(5, Direction.UP)
    e.onboard.append(rider("r", 1, 8))
    e.assigned.extend([waiting("a", 5, 9), waiting("b", 2, 1)])
    before = copy.deepcopy(e)
    choose_direction(e)
    assert e == before


def test_service_floor_reports_drop_offs_and_pickups():
    e = car(5, Direction.UP, capacity=3)
    e.onboard.extend([rider("off1", 1, 5), rider("off2", 2, 5), rider("stays", 1, 9)])
    e.assigned.extend([waiting("on", 5, 8), waiting("wrong_way", 5, 1)])
    assert service_floor(e, t=4) == ServiceResult(dropped_off=2, picked_up=1)


def test_service_floor_reports_nothing_for_a_pass_through():
    e = car(5, Direction.UP)
    e.onboard.append(rider("r", 1, 9))
    assert service_floor(e, t=4) == ServiceResult(dropped_off=0, picked_up=0)


def test_move_goes_one_floor_in_each_direction():
    up, down = car(4, Direction.UP), car(4, Direction.DOWN)
    move(up, NUM_FLOORS)
    move(down, NUM_FLOORS)
    assert (up.floor, down.floor) == (5, 3)


@pytest.mark.parametrize("floor, direction", [(NUM_FLOORS, Direction.UP), (1, Direction.DOWN)])
def test_move_past_the_building_raises(floor, direction):
    e = car(floor, direction)
    with pytest.raises(SimulationError, match="outside 1..10"):
        move(e, NUM_FLOORS)
    assert e.floor == floor
