"""Writing a finished run to CSV files."""

import csv

from conftest import pdf_sample_result, req, run_sim

from elevator_sim.output import write_outputs

FILES = ["positions.csv", "passengers.csv", "summary.csv", "elevators.csv"]


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def read_lines(path):
    return path.read_text(encoding="utf-8").splitlines()


def test_writes_four_files_into_a_new_folder(tmp_path):
    folder = tmp_path / "new" / "nested"
    paths = write_outputs(pdf_sample_result(), folder)
    assert paths == [folder / name for name in FILES]
    assert all(p.is_file() for p in paths)


def test_positions_csv_for_pdf_sample(tmp_path):
    write_outputs(pdf_sample_result(), tmp_path)
    lines = read_lines(tmp_path / "positions.csv")
    assert lines[0] == "time,elevator_0,elevator_1"
    assert len(lines) == 1 + 101
    assert lines[1:3] == ["0,1,1", "1,2,1"]
    assert lines[51] == "50,51,1"
    assert lines[-1] == "100,1,1"


def test_passengers_csv_for_pdf_sample(tmp_path):
    write_outputs(pdf_sample_result(), tmp_path)
    assert read_lines(tmp_path / "passengers.csv") == [
        "id,request_time,source,dest,elevator,pickup_time,dropoff_time,"
        "wait_time,travel_time,total_time",
        "passenger1,0,1,51,0,0,50,0,50,50",
        "passenger2,0,1,37,0,0,36,0,36,36",
        "passenger3,10,20,1,0,81,100,71,19,90",
    ]


def test_summary_csv_for_pdf_sample(tmp_path):
    write_outputs(pdf_sample_result(), tmp_path)
    assert read_lines(tmp_path / "summary.csv") == [
        "measure,min,max,mean,median,p95,passengers,final_time,scheduler,longest_wait_passenger",
        "wait,0,71,23.67,0.00,71,3,100,nearest,passenger3",
        "travel,19,50,35.00,36.00,50,3,100,nearest,passenger3",
        "total,36,90,58.67,50.00,90,3,100,nearest,passenger3",
    ]


def test_summary_csv_with_no_passengers_has_blank_stats(tmp_path):
    result, _ = run_sim([], num_elevators=2)
    write_outputs(result, tmp_path)
    assert read_lines(tmp_path / "summary.csv")[1:] == [
        "wait,,,,,,0,0,nearest,",
        "travel,,,,,,0,0,nearest,",
        "total,,,,,,0,0,nearest,",
    ]
    assert read_lines(tmp_path / "passengers.csv") == [
        "id,request_time,source,dest,elevator,pickup_time,dropoff_time,"
        "wait_time,travel_time,total_time",
    ]


def test_elevators_csv_for_pdf_sample(tmp_path):
    write_outputs(pdf_sample_result(), tmp_path)
    assert read_lines(tmp_path / "elevators.csv") == [
        "elevator,served,moving_ticks,idle_ticks,stops,peak_load",
        "0,3,100,1,5,2",
        "1,0,0,101,0,0",
    ]


def test_id_with_comma_and_quote_round_trips(tmp_path):
    tricky = 'Smith, "Jo"'
    result, _ = run_sim([req(0, tricky, 1, 3)])
    write_outputs(result, tmp_path)
    assert read_rows(tmp_path / "passengers.csv")[1][0] == tricky
    assert read_rows(tmp_path / "summary.csv")[1][-1] == tricky


def test_outputs_are_identical_across_runs(tmp_path):
    write_outputs(pdf_sample_result(), tmp_path / "a")
    write_outputs(pdf_sample_result(), tmp_path / "b")
    for name in FILES:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name


def test_files_use_unix_line_endings(tmp_path):
    for path in write_outputs(pdf_sample_result(), tmp_path):
        data = path.read_bytes()
        assert b"\r" not in data, path.name
        assert data.endswith(b"\n"), path.name


def test_existing_files_are_overwritten(tmp_path):
    (tmp_path / "summary.csv").write_text("old contents\n")
    write_outputs(pdf_sample_result(), tmp_path)
    assert read_lines(tmp_path / "summary.csv")[0].startswith("measure,")
