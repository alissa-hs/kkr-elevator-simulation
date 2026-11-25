"""End-to-end scenarios with positions and times worked out by hand. Invariant checks are on."""

import pytest
from conftest import SAMPLE_BUILDING, make_config, req, run_sim

from elevator_sim.dispatch import Dispatcher
from elevator_sim.errors import InputError, SimulationError
from elevator_sim.simulation import ElevatorStats, Simulation


def floors(result, car=0):
    """Positions of one car, tick by tick."""
    return [row[car] for _, row in result.positions]


def times(p):
    return (p.pickup_time, p.dropoff_time, p.wait_time, p.travel_time, p.total_time)


def assert_ticks_are_consecutive(result):
    assert [t for t, _ in result.positions] == list(range(result.final_time + 1))


def test_basic_trip():
    result, p = run_sim([req(0, "p1", 1, 5)])
    assert floors(result) == [1, 2, 3, 4, 5]
    assert result.final_time == 4
    assert times(p["p1"]) == (0, 4, 0, 4, 4)


def test_car_travels_to_passenger_then_reverses():
    result, p = run_sim([req(0, "p1", 5, 1)])
    assert floors(result) == [1, 2, 3, 4, 5, 4, 3, 2, 1]
    assert result.final_time == 8
    assert times(p["p1"]) == (4, 8, 4, 4, 8)


def test_pdf_sample_shows_nearest_car_weakness():
    result, p = run_sim(
        [req(0, "passenger1", 1, 51), req(0, "passenger2", 1, 37), req(10, "passenger3", 20, 1)],
        **SAMPLE_BUILDING,
    )
    assert result.final_time == 100
    assert len(result.positions) == 101
    assert_ticks_are_consecutive(result)
    assert floors(result, 0) == [1 + t for t in range(51)] + [101 - t for t in range(51, 101)]
    assert floors(result, 1) == [1] * 101
    assert {pid: x.assigned_elevator for pid, x in p.items()} == {
        "passenger1": 0, "passenger2": 0, "passenger3": 0,
    }
    assert times(p["passenger1"]) == (0, 50, 0, 50, 50)
    assert times(p["passenger2"]) == (0, 36, 0, 36, 36)
    assert times(p["passenger3"]) == (81, 100, 71, 19, 90)
    assert result.elevator_stats == [
        ElevatorStats(elevator_id=0, served=3, moving_ticks=100, idle_ticks=1, stops=5, peak_load=2),
        ElevatorStats(elevator_id=1, served=0, moving_ticks=0, idle_ticks=101, stops=0, peak_load=0),
    ]


def test_clock_ticks_through_empty_time():
    result, p = run_sim([req(5, "p1", 1, 3)])
    assert floors(result) == [1, 1, 1, 1, 1, 1, 2, 3]
    assert result.final_time == 7
    assert_ticks_are_consecutive(result)
    assert times(p["p1"]) == (5, 7, 0, 2, 2)


def test_full_car_leaves_someone_behind():
    result, p = run_sim([req(0, "a", 1, 3), req(0, "b", 1, 2)], num_floors=5, capacity=1)
    assert floors(result) == [1, 2, 3, 2, 1, 2]
    assert result.final_time == 5
    assert times(p["a"]) == (0, 2, 0, 2, 2)
    assert times(p["b"]) == (4, 5, 4, 1, 5)


def test_no_boarding_against_direction():
    result, p = run_sim([req(0, "a", 1, 8), req(2, "b", 5, 2)])
    assert floors(result) == [1, 2, 3, 4, 5, 6, 7, 8, 7, 6, 5, 4, 3, 2]
    assert result.final_time == 13
    assert (p["a"].pickup_time, p["a"].dropoff_time) == (0, 7)
    assert times(p["b"]) == (10, 13, 8, 3, 11)


def test_same_tick_pickup_from_a_moving_car():
    result, p = run_sim([req(0, "a", 1, 9), req(3, "b", 4, 6)])
    assert times(p["b"]) == (3, 5, 0, 2, 2)
    assert p["a"].dropoff_time == 8
    assert result.final_time == 8


def test_opposite_directions_at_same_floor_idle_car():
    # "first" brings the car to floor 5, where it goes idle at tick 4.
    # At tick 6 two passengers there want opposite ways; the older one (a) wins.
    result, p = run_sim([req(0, "first", 1, 5), req(6, "a", 5, 9), req(6, "b", 5, 1)])
    assert floors(result) == [1, 2, 3, 4, 5, 5, 5, 6, 7, 8, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    assert (p["a"].pickup_time, p["a"].dropoff_time) == (6, 10)
    assert times(p["b"]) == (14, 18, 8, 4, 12)
    assert result.final_time == 18


def test_second_car_is_closer():
    result, p = run_sim([req(0, "a", 1, 10), req(3, "b", 2, 1)], num_elevators=2)
    assert p["a"].assigned_elevator == 0
    assert p["b"].assigned_elevator == 1
    assert floors(result, 1) == [1, 1, 1, 1, 2, 1, 1, 1, 1, 1]
    assert times(p["b"]) == (4, 5, 1, 1, 2)
    assert p["a"].dropoff_time == 9
    assert result.final_time == 9


def test_top_floor_boundary():
    result, p = run_sim([req(0, "a", 10, 1)])
    assert floors(result) == list(range(1, 11)) + list(range(9, 0, -1))
    assert max(floors(result)) == 10
    assert times(p["a"]) == (9, 18, 9, 9, 18)
    assert result.final_time == 18


def test_empty_input():
    result, p = run_sim([], num_elevators=2)
    assert result.positions == [(0, [1, 1])]
    assert result.final_time == 0
    assert p == {}


@pytest.mark.parametrize("max_ticks", [3, 7])
def test_max_ticks_below_final_time_raises(max_ticks):
    with pytest.raises(SimulationError, match=f"max_ticks={max_ticks}"):
        run_sim([req(0, "p1", 5, 1)], max_ticks=max_ticks)


def test_max_ticks_equal_to_final_time_succeeds():
    result, _ = run_sim([req(0, "p1", 5, 1)], max_ticks=8)
    assert result.final_time == 8
    assert len(result.positions) == 9


def test_per_elevator_stats():
    result, _ = run_sim([req(0, "p1", 1, 5)])
    assert result.elevator_stats == [
        ElevatorStats(elevator_id=0, served=1, moving_ticks=4, idle_ticks=1, stops=2, peak_load=1)
    ]


class RecordingDispatcher(Dispatcher):
    """Sends everyone to car 0 and records (t, request_time) for every call."""

    name = "recording"

    def __init__(self, config):
        super().__init__(config)
        self.calls = []

    def assign(self, passenger, elevators, t):
        self.calls.append((t, passenger.request_time))
        return 0


def test_dispatcher_only_sees_requests_at_their_own_time():
    requests = [req(7, "d", 2, 9), req(0, "a", 1, 5), req(3, "c", 6, 2), req(0, "b", 4, 8)]
    recorder = RecordingDispatcher(make_config())
    run_sim(requests, dispatcher=recorder)
    assert len(recorder.calls) == len(requests)
    assert all(t == request_time for t, request_time in recorder.calls)


def test_result_reports_injected_dispatcher_name():
    result, _ = run_sim([req(0, "a", 1, 3)], dispatcher=RecordingDispatcher(make_config()))
    assert result.scheduler_name == "recording"
    assert result.config.scheduler == "nearest"


def test_default_dispatcher_comes_from_config():
    result, _ = run_sim([req(0, "a", 1, 3)])
    assert result.scheduler_name == "nearest"


@pytest.mark.parametrize("bad_answer", [2, -1, True, "0"])
def test_dispatcher_returning_invalid_car_raises(bad_answer):
    class Broken(Dispatcher):
        name = "broken"

        def assign(self, passenger, elevators, t):
            return bad_answer

    with pytest.raises(SimulationError, match="invalid elevator id"):
        run_sim([req(0, "a", 1, 3)], num_elevators=2, dispatcher=Broken(make_config()))


def test_run_can_only_be_called_once():
    sim = Simulation(make_config(), [req(0, "a", 1, 3)])
    sim.run()
    with pytest.raises(SimulationError, match="only be called once"):
        sim.run()


def test_invalid_requests_are_rejected_before_running():
    with pytest.raises(InputError, match="floor 11 is above --floors 10"):
        Simulation(make_config(), [req(0, "a", 1, 11)])
