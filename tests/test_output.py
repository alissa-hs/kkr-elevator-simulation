"""Writing a finished run to CSV files."""

import csv
from pathlib import Path

import pytest
from conftest import pdf_sample_result, req, run_sim

from elevator_sim.output import write_outputs

FILES = ["positions.csv", "passengers.csv", "summary.csv", "elevators.csv", "report.html", "run.json"]
OUT = Path("output")


@pytest.fixture(autouse=True)
def _run_in_temp_folder(tmp_path, monkeypatch):
    """Run each test from an empty temp folder, so output/ is created there, not in the project."""
    monkeypatch.chdir(tmp_path)


def write(result):
    """Write outputs and return the run folder they went into."""
    return write_outputs(result)[0].parent


def read_rows(folder, name):
    with open(folder / name, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def read_lines(folder, name):
    return (folder / name).read_text(encoding="utf-8").splitlines()


def test_first_run_writes_six_files_into_run_001():
    assert not OUT.exists()
    paths = write_outputs(pdf_sample_result())
    assert paths == [OUT / "run_001" / name for name in FILES]
    assert all(p.is_file() for p in paths)


def test_each_run_gets_the_next_number_and_earlier_runs_are_kept():
    first = write(pdf_sample_result())
    second = write(pdf_sample_result())
    assert (first.name, second.name) == ("run_001", "run_002")
    assert all((first / name).is_file() for name in FILES)


def test_numbering_continues_after_the_highest_run_and_ignores_other_entries():
    for name in ["run_001", "run_007", "notes", "run_abc"]:
        (OUT / name).mkdir(parents=True)
    (OUT / "run_050").write_text("a file, not a folder\n")
    assert write(pdf_sample_result()).name == "run_008"


def test_runs_past_999_keep_counting():
    (OUT / "run_999").mkdir(parents=True)
    assert write(pdf_sample_result()).name == "run_1000"


def test_positions_csv_for_pdf_sample():
    lines = read_lines(write(pdf_sample_result()), "positions.csv")
    assert lines[0] == "time,elevator_0,elevator_1"
    assert len(lines) == 1 + 101
    assert lines[1:3] == ["0,1,1", "1,2,1"]
    assert lines[51] == "50,51,1"
    assert lines[-1] == "100,1,1"


def test_passengers_csv_for_pdf_sample():
    assert read_lines(write(pdf_sample_result()), "passengers.csv") == [
        "id,request_time,source,dest,elevator,pickup_time,dropoff_time,"
        "wait_time,travel_time,total_time",
        "passenger1,0,1,51,0,0,50,0,50,50",
        "passenger2,0,1,37,0,0,36,0,36,36",
        "passenger3,10,20,1,0,81,100,71,19,90",
    ]


def test_summary_csv_for_pdf_sample():
    assert read_lines(write(pdf_sample_result()), "summary.csv") == [
        "measure,min,max,mean,median,p95,passengers,final_time,dispatcher,longest_wait_passenger",
        "wait,0,71,23.67,0.00,71,3,100,nearest,passenger3",
        "travel,19,50,35.00,36.00,50,3,100,nearest,passenger3",
        "total,36,90,58.67,50.00,90,3,100,nearest,passenger3",
    ]


def test_summary_csv_with_no_passengers_has_blank_stats():
    result, _ = run_sim([], num_elevators=2)
    folder = write(result)
    assert read_lines(folder, "summary.csv")[1:] == [
        "wait,,,,,,0,0,nearest,",
        "travel,,,,,,0,0,nearest,",
        "total,,,,,,0,0,nearest,",
    ]
    assert read_lines(folder, "passengers.csv") == [
        "id,request_time,source,dest,elevator,pickup_time,dropoff_time,"
        "wait_time,travel_time,total_time",
    ]


def test_elevators_csv_for_pdf_sample():
    assert read_lines(write(pdf_sample_result()), "elevators.csv") == [
        "elevator,served,moving_ticks,idle_ticks,stops,peak_load",
        "0,3,100,1,5,2",
        "1,0,0,101,0,0",
    ]


def test_id_with_comma_and_quote_round_trips():
    tricky = 'Smith, "Jo"'
    result, _ = run_sim([req(0, tricky, 1, 3)])
    folder = write(result)
    assert read_rows(folder, "passengers.csv")[1][0] == tricky
    assert read_rows(folder, "summary.csv")[1][-1] == tricky


def test_outputs_are_identical_across_runs():
    first = {p.name: p.read_bytes() for p in write_outputs(pdf_sample_result())}
    second = {p.name: p.read_bytes() for p in write_outputs(pdf_sample_result())}
    assert first == second


def test_files_use_unix_line_endings():
    for path in write_outputs(pdf_sample_result()):
        data = path.read_bytes()
        assert b"\r" not in data, path.name
        assert data.endswith(b"\n"), path.name
