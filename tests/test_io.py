"""Reading requests from CSV, and request validation."""

from pathlib import Path

import pytest
from conftest import make_config

from elevator_sim.errors import InputError
from elevator_sim.io import load_requests_csv, validate_requests
from elevator_sim.models import Request

EXAMPLES = Path(__file__).parent.parent / "examples"


def csv_file(tmp_path, text, encoding="utf-8"):
    path = tmp_path / "requests.csv"
    path.write_text(text, encoding=encoding)
    return path


def load_error_lines(path):
    with pytest.raises(InputError) as exc:
        load_requests_csv(path)
    return str(exc.value).splitlines()


def fields(requests):
    return [(r.time, r.passenger_id, r.source, r.dest, r.input_order, r.line) for r in requests]


PDF_SAMPLE_FIELDS = [
    (0, "passenger1", 1, 51, 0, 2),
    (0, "passenger2", 1, 37, 1, 3),
    (10, "passenger3", 20, 1, 2, 4),
]


# --- Loading ---------------------------------------------------------------


def test_load_pdf_sample_file():
    assert fields(load_requests_csv(EXAMPLES / "sample.csv")) == PDF_SAMPLE_FIELDS


def test_template_file_loads_with_no_requests():
    assert load_requests_csv(EXAMPLES / "template.csv") == []


def test_spaces_around_fields_and_header_are_ignored(tmp_path):
    path = csv_file(tmp_path, (
        " time , id , source , dest \n"
        " 0 , passenger1 , 1 , 51\n"
        "0,  passenger2,1 ,37\n"
        "  10,passenger3 ,20,  1  \n"
    ))
    assert fields(load_requests_csv(path)) == PDF_SAMPLE_FIELDS


def test_wrong_header_is_rejected(tmp_path):
    path = csv_file(tmp_path, "time,id,from,to\n0,a,1,3\n")
    assert load_error_lines(path) == [
        "line 1: header must be time,id,source,dest, got 'time,id,from,to'"
    ]


def test_missing_header_is_rejected(tmp_path):
    path = csv_file(tmp_path, "0,a,1,3\n")
    assert load_error_lines(path) == ["line 1: header must be time,id,source,dest, got '0,a,1,3'"]


def test_empty_file_is_rejected(tmp_path):
    assert load_error_lines(csv_file(tmp_path, "")) == [
        "file is empty; expected header time,id,source,dest"
    ]


def test_missing_file_is_an_input_error(tmp_path):
    with pytest.raises(InputError, match="cannot read"):
        load_requests_csv(tmp_path / "nope.csv")


def test_non_number_field_names_its_line(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n0,a,1,3\nabc,b,2,4\n")
    assert load_error_lines(path) == ["line 3: time 'abc' is not a whole number"]


@pytest.mark.parametrize("value", ["1.5", "1e3", "1_000", "", " "])
def test_only_plain_whole_numbers_are_accepted(tmp_path, value):
    path = csv_file(tmp_path, f"time,id,source,dest\n0,a,{value},3\n")
    assert load_error_lines(path) == [f"line 2: source '{value.strip()}' is not a whole number"]


def test_wrong_field_count_is_rejected(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n0,a,1\n0,b,1,3,9\n")
    assert load_error_lines(path) == [
        "line 2: expected 4 fields, got 3",
        "line 3: expected 4 fields, got 5",
    ]


def test_empty_id_is_rejected(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n0, ,1,3\n")
    assert load_error_lines(path) == ["line 2: id is empty"]


def test_row_rules_are_checked_at_load(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n-1,a,1,3\n0,b,4,4\n0,c,1,3\n2,c,5,2\n")
    assert load_error_lines(path) == [
        "line 2: time -1 is negative",
        "line 3: source and dest are both floor 4",
        "line 4: duplicate id 'c'",
        "line 5: duplicate id 'c'",
    ]


def test_every_bad_row_is_listed_in_line_order(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n0,a,1,1\nx,b,1,3\n0,c\n0,d,1,3\n")
    assert load_error_lines(path) == [
        "line 2: source and dest are both floor 1",
        "line 3: time 'x' is not a whole number",
        "line 4: expected 4 fields, got 2",
    ]


def test_header_only_gives_no_requests(tmp_path):
    assert load_requests_csv(csv_file(tmp_path, "time,id,source,dest\n")) == []


def test_trailing_blank_lines_are_ignored(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n0,a,1,3\n\n   \n\n")
    assert fields(load_requests_csv(path)) == [(0, "a", 1, 3, 0, 2)]


def test_blank_line_between_rows_keeps_order_and_line_numbers(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n0,a,1,3\n\n1,b,2,5\n2,c,4,1\n")
    assert fields(load_requests_csv(path)) == [
        (0, "a", 1, 3, 0, 2),
        (1, "b", 2, 5, 1, 4),
        (2, "c", 4, 1, 2, 5),
    ]
    bad = csv_file(tmp_path, "time,id,source,dest\n0,a,1,3\n\n1,b,2,2\n")
    assert load_error_lines(bad) == ["line 4: source and dest are both floor 2"]


def test_rows_out_of_time_order_are_accepted(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n9,late,1,3\n0,early,2,4\n")
    assert [r.passenger_id for r in load_requests_csv(path)] == ["late", "early"]


def test_excel_byte_order_mark_is_accepted(tmp_path):
    path = csv_file(tmp_path, "time,id,source,dest\n0,a,1,3\n", encoding="utf-8-sig")
    assert fields(load_requests_csv(path)) == [(0, "a", 1, 3, 0, 2)]


def test_quoted_id_with_comma_and_quote_is_read(tmp_path):
    path = csv_file(tmp_path, 'time,id,source,dest\n0,"Smith, ""Jo""",1,3\n')
    assert load_requests_csv(path)[0].passenger_id == 'Smith, "Jo"'


def test_requests_differing_only_in_line_are_equal():
    a = Request(0, "a", 1, 3, input_order=0, line=2)
    b = Request(0, "a", 1, 3, input_order=0, line=7)
    assert a == b
    assert hash(a) == hash(b)


# --- Validation ------------------------------------------------------------


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
