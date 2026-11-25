"""The command line: python -m elevator_sim / elevator-sim."""

import subprocess
import sys
from pathlib import Path

import pytest

from elevator_sim.cli import main

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample.csv")
SAMPLE_FLAGS = ["--input", SAMPLE, "--floors", "100", "--elevators", "2", "--capacity", "10"]
FILES = ["positions.csv", "passengers.csv", "summary.csv", "elevators.csv"]


@pytest.fixture(autouse=True)
def _run_in_temp_folder(tmp_path, monkeypatch):
    """Run each test from an empty temp folder, so output/ is created there, not in the project."""
    monkeypatch.chdir(tmp_path)


def run_cli(args, capsys):
    """Return (exit code, stdout, stderr), including argparse's own exits."""
    try:
        code = main(args)
    except SystemExit as exc:
        code = exc.code
    out = capsys.readouterr()
    return code, out.out, out.err


def with_flag(name, value):
    """SAMPLE_FLAGS with one flag's value replaced."""
    args = list(SAMPLE_FLAGS)
    args[args.index(name) + 1] = value
    return args


def without_flag(name):
    args = list(SAMPLE_FLAGS)
    i = args.index(name)
    return args[:i] + args[i + 2:]


def test_pdf_sample_run_writes_run_folder_and_exits_0(capsys):
    code, out, err = run_cli(SAMPLE_FLAGS, capsys)
    assert code == 0
    assert err == ""
    assert out == "Wrote " + ", ".join(f"output/run_001/{f}" for f in FILES) + "\n"
    assert all((Path("output/run_001") / f).is_file() for f in FILES)
    summary = (Path("output/run_001") / "summary.csv").read_text().splitlines()
    assert summary[1] == "wait,0,71,23.67,0.00,71,3,100,nearest,passenger3"


def test_second_run_writes_run_002(capsys):
    run_cli(SAMPLE_FLAGS, capsys)
    code, out, _ = run_cli(SAMPLE_FLAGS, capsys)
    assert code == 0
    assert "output/run_002/positions.csv" in out
    assert Path("output/run_001/positions.csv").is_file()


def test_floors_too_low_exits_2_with_hint(capsys):
    code, out, err = run_cli(with_flag("--floors", "10"), capsys)
    assert code == 2
    assert out == ""
    assert err.splitlines() == [
        "error: line 2: floor 51 is above --floors 10",
        "line 3: floor 37 is above --floors 10",
        "line 4: floor 20 is above --floors 10",
        "use --floors 51 or higher",
    ]
    assert not Path("output").exists()


@pytest.mark.parametrize("flag", ["--input", "--floors", "--elevators", "--capacity"])
def test_missing_required_flag_exits_2(flag, capsys):
    code, _, err = run_cli(without_flag(flag), capsys)
    assert code == 2
    assert f"the following arguments are required: {flag}" in err


def test_bad_settings_exit_2(capsys):
    code, _, err = run_cli(with_flag("--capacity", "0"), capsys)
    assert code == 2
    assert err == "error: capacity must be >= 1, got 0\n"


def test_non_number_setting_exits_2(capsys):
    code, _, err = run_cli(with_flag("--floors", "ten"), capsys)
    assert code == 2
    assert "invalid int value: 'ten'" in err


def test_unknown_dispatcher_exits_2(capsys):
    code, _, err = run_cli(SAMPLE_FLAGS + ["--dispatcher", "fastest"], capsys)
    assert code == 2
    assert "invalid choice: 'fastest'" in err


def test_dispatcher_flag_is_accepted(capsys):
    code, _, _ = run_cli(SAMPLE_FLAGS + ["--dispatcher", "nearest"], capsys)
    assert code == 0


def test_missing_input_file_exits_2(capsys):
    code, _, err = run_cli(with_flag("--input", "nope.csv"), capsys)
    assert code == 2
    assert err.startswith("error: cannot read nope.csv")


def test_bad_csv_row_exits_2(tmp_path, capsys):
    bad = tmp_path / "bad.csv"
    bad.write_text("time,id,source,dest\nsoon,a,1,3\n")
    code, _, err = run_cli(with_flag("--input", str(bad)), capsys)
    assert code == 2
    assert err == "error: line 2: time 'soon' is not a whole number\n"


def test_stuck_simulation_exits_3(monkeypatch, capsys):
    monkeypatch.setattr("elevator_sim.simulation.move", lambda elevator, num_floors: None)
    code, out, err = run_cli(SAMPLE_FLAGS, capsys)
    assert code == 3
    assert out == ""
    assert err.startswith("simulation failed: tick ")
    assert "starvation limit" in err
    assert not Path("output").exists()


def test_errors_have_no_traceback(capsys):
    for args in (with_flag("--floors", "10"), with_flag("--input", "nope.csv")):
        _, _, err = run_cli(args, capsys)
        assert "Traceback" not in err


def test_invariant_checks_are_not_a_cli_option(capsys):
    code, _, err = run_cli(SAMPLE_FLAGS + ["--check-invariants"], capsys)
    assert code == 2
    assert "unrecognized arguments: --check-invariants" in err
    assert "invariant" not in run_cli(["--help"], capsys)[1]


def test_python_dash_m_runs_the_cli(tmp_path):
    done = subprocess.run(
        [sys.executable, "-m", "elevator_sim", *SAMPLE_FLAGS],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("Wrote output/run_001/positions.csv")
