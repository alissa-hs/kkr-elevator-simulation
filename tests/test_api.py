"""simulate(): running from Python."""

import pytest
from conftest import SAMPLE_BUILDING, pdf_sample_result

from elevator_sim import Request, simulate
from elevator_sim.errors import ConfigError, InputError

PDF_SAMPLE_TUPLES = [(0, "passenger1", 1, 51), (0, "passenger2", 1, 37), (10, "passenger3", 20, 1)]


def passenger_rows(result):
    return [(p.id, p.assigned_elevator, p.pickup_time, p.dropoff_time) for p in result.passengers]


def test_simulate_pdf_sample_from_tuples():
    result = simulate(PDF_SAMPLE_TUPLES, **SAMPLE_BUILDING)
    expected = pdf_sample_result()
    assert result.final_time == 100
    assert result.positions == expected.positions
    assert passenger_rows(result) == passenger_rows(expected)
    assert result.dispatcher_name == "nearest"


def test_tuples_and_request_objects_give_the_same_result():
    objects = [Request(*t, input_order=i) for i, t in enumerate(PDF_SAMPLE_TUPLES)]
    from_tuples = simulate(PDF_SAMPLE_TUPLES, **SAMPLE_BUILDING)
    from_objects = simulate(objects, **SAMPLE_BUILDING)
    assert from_objects.positions == from_tuples.positions
    assert passenger_rows(from_objects) == passenger_rows(from_tuples)


def test_tuple_position_breaks_ties_between_same_time_requests():
    result = simulate([(0, "second_in_list", 1, 5), (0, "first_in_list", 1, 5)],
                      num_floors=10, num_elevators=1, capacity=1)
    first = {p.id: p.pickup_time for p in result.passengers}
    assert first["second_in_list"] < first["first_in_list"]


def test_simulate_writes_no_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    simulate(PDF_SAMPLE_TUPLES, **SAMPLE_BUILDING)
    assert list(tmp_path.iterdir()) == []


def test_bad_tuples_are_all_listed_and_named():
    bad = [
        (0, "short", 1),
        (0, "", 1, 3),
        ("0", "text_time", 1, 3),
        (0, "bool_floor", True, 3),
        (0, "fine", 1, 3),
    ]
    with pytest.raises(InputError) as exc:
        simulate(bad, num_floors=10, num_elevators=1, capacity=4)
    assert str(exc.value).splitlines() == [
        "request at position 0: expected (time, id, source, dest), got (0, 'short', 1)",
        "request at position 1: id must be a non-empty string, got ''",
        "request 'text_time': time must be a whole number, got '0'",
        "request 'bool_floor': source must be a whole number, got True",
    ]


def test_floor_too_high_in_tuple_names_the_request():
    with pytest.raises(InputError) as exc:
        simulate([(0, "visitor", 1, 75)], num_floors=60, num_elevators=1, capacity=4)
    assert str(exc.value).splitlines() == [
        "request 'visitor': floor 75 is above --floors 60",
        "use --floors 75 or higher",
    ]


def test_missing_building_setting_raises_config_error():
    with pytest.raises(ConfigError, match=r"missing required setting\(s\): capacity$"):
        simulate(PDF_SAMPLE_TUPLES, num_floors=100, num_elevators=2)


def test_unknown_dispatcher_raises_config_error():
    with pytest.raises(ConfigError, match="unknown dispatcher 'fastest'"):
        simulate(PDF_SAMPLE_TUPLES, **SAMPLE_BUILDING, dispatcher="fastest")


def test_dispatcher_is_chosen_by_name():
    result = simulate(PDF_SAMPLE_TUPLES, **SAMPLE_BUILDING, dispatcher="nearest")
    assert result.dispatcher_name == "nearest"
    assert result.config.dispatcher == "nearest"
