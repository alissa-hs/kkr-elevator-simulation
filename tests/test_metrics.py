"""Summary statistics."""

import copy

import pytest
from conftest import make_config, pdf_sample_result, run_sim

from elevator_sim.metrics import Stats, compute_stats, compute_summary
from elevator_sim.models import Passenger, PassengerState
from elevator_sim.simulation import ElevatorStats, SimulationResult


def delivered(pid, request_time, pickup, dropoff, input_order):
    return Passenger(pid, request_time, source=1, dest=3, input_order=input_order,
                     assigned_elevator=0, state=PassengerState.DELIVERED,
                     pickup_time=pickup, dropoff_time=dropoff)


def test_stats_for_pdf_sample_waits():
    s = compute_stats([0, 0, 71])
    assert (s.min, s.max, s.median, s.p95) == (0, 71, 0, 71)
    assert s.mean == pytest.approx(23.6667, abs=1e-4)


def test_stats_for_a_single_value():
    assert compute_stats([7]) == Stats(min=7, max=7, mean=7, median=7, p95=7)


def test_median_of_even_count_averages_the_middle_two():
    s = compute_stats([4, 1, 3, 2])
    assert s.median == 2.5
    assert s.p95 == 4


def test_p95_uses_nearest_rank():
    # Position ceil(0.95 * n), counting from 1.
    assert compute_stats(list(range(1, 21))).p95 == 19  # ceil(19.0)
    assert compute_stats(list(range(1, 22))).p95 == 20  # ceil(19.95)
    assert compute_stats(list(range(1, 101))).p95 == 95  # ceil(95.0)


def test_stats_with_no_values_are_none():
    assert compute_stats([]) == Stats(min=None, max=None, mean=None, median=None, p95=None)


def test_longest_wait_tie_goes_to_earliest_request():
    later = delivered("later", request_time=5, pickup=10, dropoff=12, input_order=1)
    earlier = delivered("earlier", request_time=0, pickup=5, dropoff=7, input_order=0)
    result = SimulationResult(
        config=make_config(), positions=[], passengers=[later, earlier], final_time=12,
        dispatcher_name="nearest", elevator_stats=[],
    )
    assert compute_summary(result).max_wait_passenger_id == "earlier"


def test_summary_includes_per_car_stats():
    summary = compute_summary(pdf_sample_result())
    assert summary.passenger_count == 3
    assert summary.final_time == 100
    assert summary.dispatcher_name == "nearest"
    assert summary.max_wait_passenger_id == "passenger3"
    assert summary.elevators == (
        ElevatorStats(elevator_id=0, served=3, moving_ticks=100, idle_ticks=1, stops=5, peak_load=2),
        ElevatorStats(elevator_id=1, served=0, moving_ticks=0, idle_ticks=101, stops=0, peak_load=0),
    )


def test_pdf_sample_wait_travel_and_total_stats():
    summary = compute_summary(pdf_sample_result())
    assert (summary.wait.min, summary.wait.max, summary.wait.median, summary.wait.p95) == (0, 71, 0, 71)
    assert summary.wait.mean == pytest.approx(71 / 3)
    assert summary.travel == Stats(min=19, max=50, mean=35, median=36, p95=50)
    assert (summary.total.min, summary.total.max, summary.total.median, summary.total.p95) == (
        36, 90, 50, 90,
    )
    assert summary.total.mean == pytest.approx(176 / 3)


def test_empty_run_summary_has_no_stats_but_keeps_cars():
    result, _ = run_sim([], num_elevators=2)
    summary = compute_summary(result)
    assert summary.passenger_count == 0
    assert summary.max_wait_passenger_id is None
    assert summary.wait == summary.travel == summary.total == Stats()
    assert summary.elevators == (
        ElevatorStats(elevator_id=0, idle_ticks=1),
        ElevatorStats(elevator_id=1, idle_ticks=1),
    )


def test_compute_summary_does_not_change_the_result():
    result = pdf_sample_result()
    before = copy.deepcopy(result)
    compute_summary(result)
    assert result == before
