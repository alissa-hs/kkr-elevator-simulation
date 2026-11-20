from elevator_sim.models import Direction, Elevator, Passenger, PassengerState, Request


def make_passenger(pid="p", source=1, dest=5, request_time=0, input_order=0):
    return Passenger(id=pid, request_time=request_time, source=source, dest=dest,
                     input_order=input_order)


def test_direction_opposite_stays_a_direction():
    assert Direction.UP.opposite is Direction.DOWN
    assert Direction.DOWN.opposite is Direction.UP
    assert Direction.IDLE.opposite is Direction.IDLE


def test_request_direction_and_label():
    assert Request(0, "a", 1, 5).direction is Direction.UP
    assert Request(0, "a", 5, 1).direction is Direction.DOWN
    assert Request(0, "a", 1, 5).label == "request 'a'"
    assert Request(0, "a", 1, 5, line=3).label == "line 3"


def test_passenger_from_request_and_times():
    p = Passenger.from_request(Request(2, "a", 1, 5, input_order=4))
    assert (p.id, p.request_time, p.source, p.dest, p.input_order) == ("a", 2, 1, 5, 4)
    assert p.state is PassengerState.WAITING and p.assigned_elevator is None
    assert p.sort_key == (2, 4)
    assert p.wait_time is None and p.travel_time is None and p.total_time is None
    p.pickup_time = 5
    assert p.wait_time is None  # None until delivered
    p.dropoff_time = 9
    assert (p.wait_time, p.travel_time, p.total_time) == (3, 4, 7)


def test_elevator_helpers():
    e = Elevator(id=0, floor=5, capacity=2)
    assert e.prev_floor == 5 and e.is_idle and e.load == 0 and not e.is_full
    rider = make_passenger("r", source=1, dest=8)
    late = make_passenger("late", source=5, dest=1, request_time=3)
    early = make_passenger("early", source=5, dest=9, request_time=1)
    below = make_passenger("below", source=2, dest=3)
    e.onboard.append(rider)
    e.assigned.extend([late, early, below])
    assert e.targets() == {8, 5, 2}
    assert e.has_target_in(Direction.UP) and e.has_target_in(Direction.DOWN)
    assert not e.has_target_in(Direction.IDLE)
    assert [p.id for p in e.waiting_here()] == ["early", "late"]
    e.onboard.append(make_passenger("r2"))
    assert e.is_full


def test_has_target_in_is_strict():
    e = Elevator(id=0, floor=5, capacity=1)
    e.assigned.append(make_passenger(source=5, dest=9))
    assert not e.has_target_in(Direction.UP)
    assert not e.has_target_in(Direction.DOWN)
