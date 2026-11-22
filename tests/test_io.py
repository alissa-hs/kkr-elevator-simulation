"""Request validation. CSV loading tests are added in step 9."""

import pytest
from conftest import make_config

from elevator_sim.errors import InputError
from elevator_sim.io import validate_requests
from elevator_sim.models import Request


def from_file(line, time, pid, source, dest):
    """A request as the CSV loader will build it: line set, input_order = line - 2."""
    return Request(time, pid, source, dest, input_order=line - 2, line=line)


def error_lines(requests, **config):
    with pytest.raises(InputError) as exc:
        validate_requests(requests, make_config(**config))
    return str(exc.value).splitlines()


def test_valid_requests_pass():
    validate_requests([Request(0, "a", 1, 10), Request(3, "b", 10, 1)], make_config())


def test_empty_list_passes():
    validate_requests([], make_config())


def test_floors_above_building_list_each_row_and_one_hint():
    pdf_sample = [
        from_file(2, 0, "passenger1", 1, 51),
        from_file(3, 0, "passenger2", 1, 37),
        from_file(4, 10, "passenger3", 20, 1),
    ]
    assert error_lines(pdf_sample, num_floors=10) == [
        "line 2: floor 51 is above --floors 10",
        "line 3: floor 37 is above --floors 10",
        "line 4: floor 20 is above --floors 10",
        "use --floors 51 or higher",
    ]


def test_floor_below_one_has_no_hint():
    assert error_lines([from_file(4, 0, "a", 0, 3)]) == ["line 4: floor 0 is below 1"]


def test_code_built_request_is_named_by_id():
    lines = error_lines([Request(0, "visitor", 1, 75)], num_floors=60)
    assert lines == ["request 'visitor': floor 75 is above --floors 60", "use --floors 75 or higher"]
    assert not any(line.startswith("line") for line in lines)


def test_negative_time_is_rejected():
    assert error_lines([Request(-1, "a", 1, 3)]) == ["request 'a': time -1 is negative"]


def test_same_source_and_dest_is_rejected():
    assert error_lines([Request(0, "a", 4, 4)]) == ["request 'a': source and dest are both floor 4"]


def test_duplicate_id_reports_every_row():
    requests = [from_file(2, 0, "dup", 1, 3), from_file(3, 0, "ok", 1, 3), from_file(4, 1, "dup", 2, 5)]
    assert error_lines(requests) == [
        "line 2: duplicate id 'dup'",
        "line 4: duplicate id 'dup'",
    ]


def test_every_problem_is_listed_in_one_error():
    requests = [
        Request(-2, "neg", 1, 3),
        Request(0, "same", 5, 5),
        Request(0, "high", 1, 12),
        Request(0, "low", 0, 4),
    ]
    assert error_lines(requests) == [
        "request 'neg': time -2 is negative",
        "request 'same': source and dest are both floor 5",
        "request 'high': floor 12 is above --floors 10",
        "request 'low': floor 0 is below 1",
        "use --floors 12 or higher",
    ]


def test_same_bad_floor_for_source_and_dest_is_reported_once():
    assert error_lines([Request(0, "a", 12, 12)]) == [
        "request 'a': source and dest are both floor 12",
        "request 'a': floor 12 is above --floors 10",
        "use --floors 12 or higher",
    ]
