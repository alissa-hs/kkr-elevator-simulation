"""Each rule is broken on purpose to prove the checker catches it."""

import pytest
from conftest import make_config

from elevator_sim.errors import SimulationError
from elevator_sim.invariants import check_invariants
from elevator_sim.models import Direction, Elevator, Passenger, PassengerState

CONFIG = make_config(num_floors=10, num_elevators=2, capacity=2)


def valid_state():
    """Two cars: car 0 going up with a rider and a pickup, car 1 idle. One passenger delivered."""
    car0 = Elevator(id=0, floor=4, capacity=2, direction=Direction.UP, prev_floor=3)
    car1 = Elevator(id=1, floor=1, capacity=2)
    rider = Passenger("rider", request_time=0, source=1, dest=8, input_order=0,
                      assigned_elevator=0, state=PassengerState.RIDING, pickup_time=1)
    waiting = Passenger("waiting", request_time=2, source=6, dest=9, input_order=1,
                        assigned_elevator=0)
    done = Passenger("done", request_time=0, source=1, dest=3, input_order=2,
                     assigned_elevator=1, state=PassengerState.DELIVERED,
                     pickup_time=0, dropoff_time=2)
    car0.onboard.append(rider)
    car0.assigned.append(waiting)
    return [car0, car1], [rider, waiting, done]


def check(elevators, passengers):
    check_invariants(5, elevators, passengers, CONFIG)


def test_valid_state_passes():
    check(*valid_state())


def test_car_outside_building_breaks_rule_1():
    cars, people = valid_state()
    cars[1].floor = cars[1].prev_floor = 11
    with pytest.raises(SimulationError, match=r"tick 5, elevator 1, rule 1: floor 11"):
        check(cars, people)


def test_car_moving_two_floors_breaks_rule_1():
    cars, people = valid_state()
    cars[0].prev_floor = 2
    with pytest.raises(SimulationError, match=r"elevator 0, rule 1: moved from floor 2 to 4"):
        check(cars, people)


def test_over_capacity_breaks_rule_2():
    cars, people = valid_state()
    extra = [Passenger(f"x{i}", 0, 1, 9, 10 + i, assigned_elevator=0,
                       state=PassengerState.RIDING, pickup_time=0) for i in range(2)]
    cars[0].onboard.extend(extra)
    with pytest.raises(SimulationError, match=r"elevator 0, rule 2: 3 riders exceed capacity 2"):
        check(cars, people + extra)


def test_passenger_in_two_places_breaks_rule_3():
    cars, people = valid_state()
    cars[1].assigned.append(people[1])
    with pytest.raises(SimulationError, match=r"rule 3: passenger 'waiting' is in 2 places"):
        check(cars, people)


def test_lost_passenger_breaks_rule_3():
    cars, people = valid_state()
    cars[0].assigned.clear()
    with pytest.raises(SimulationError, match=r"rule 3: passenger 'waiting' is in no car"):
        check(cars, people)


def test_unreleased_passenger_in_a_car_breaks_rule_3():
    cars, people = valid_state()
    with pytest.raises(SimulationError, match=r"rule 3: passenger 'waiting' .* never released"):
        check(cars, [people[0], people[2]])


def test_passenger_in_wrong_car_breaks_rule_4():
    cars, people = valid_state()
    people[1].assigned_elevator = 1
    with pytest.raises(SimulationError, match=r"elevator 0, rule 4: passenger 'waiting'"):
        check(cars, people)


def test_state_not_matching_place_breaks_rule_5():
    cars, people = valid_state()
    people[1].state = PassengerState.RIDING
    with pytest.raises(SimulationError, match=r"rule 5: passenger 'waiting' is RIDING, expected WAITING"):
        check(cars, people)


def test_pickup_before_request_breaks_rule_6():
    cars, people = valid_state()
    people[0].request_time = 3
    with pytest.raises(SimulationError, match=r"rule 6: passenger 'rider' picked up at 1"):
        check(cars, people)


def test_dropoff_not_after_pickup_breaks_rule_6():
    cars, people = valid_state()
    people[2].dropoff_time = 0
    with pytest.raises(SimulationError, match=r"rule 6: passenger 'done' dropped off at 0"):
        check(cars, people)


def test_rider_destination_behind_breaks_rule_7():
    cars, people = valid_state()
    people[0].dest = 2
    with pytest.raises(SimulationError, match=r"elevator 0, rule 7: rider 'rider'"):
        check(cars, people)


def test_rider_at_destination_floor_breaks_rule_7():
    cars, people = valid_state()
    people[0].dest = 4  # should have been unloaded at this floor
    with pytest.raises(SimulationError, match=r"rule 7"):
        check(cars, people)


def test_idle_car_with_riders_breaks_rule_8():
    cars, people = valid_state()
    cars[0].direction = Direction.IDLE
    with pytest.raises(SimulationError, match=r"elevator 0, rule 8: idle with 1 rider"):
        check(cars, people)
