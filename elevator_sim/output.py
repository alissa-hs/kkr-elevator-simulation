"""Writing a finished run to CSV files and an HTML report.

Kept apart from io.py because it needs metrics (and so simulation), while
simulation itself imports io for request validation.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Iterable
from pathlib import Path

from elevator_sim.metrics import Stats, compute_summary
from elevator_sim.report import REPORT_FILE, build_report
from elevator_sim.simulation import SimulationResult

OUTPUT_DIR = Path("output")
"""Relative to the folder the program is run from. Each run gets its own run_NNN folder inside."""
RUN_FOLDER = re.compile(r"run_([0-9]+)")

POSITIONS_FILE = "positions.csv"
PASSENGERS_FILE = "passengers.csv"
SUMMARY_FILE = "summary.csv"
ELEVATORS_FILE = "elevators.csv"
RUN_INFO_FILE = "run.json"
FROM_CODE = "(from code)"
"""run.json's input when the run didn't come from a CSV file (e.g. simulate())."""

PASSENGER_COLUMNS = (
    "id", "request_time", "source", "dest", "elevator",
    "pickup_time", "dropoff_time", "wait_time", "travel_time", "total_time",
)
SUMMARY_COLUMNS = (
    "measure", "min", "max", "mean", "median", "p95",
    "passengers", "final_time", "dispatcher", "longest_wait_passenger",
)
ELEVATOR_COLUMNS = ("elevator", "served", "moving_ticks", "idle_ticks", "stops", "peak_load")


def write_outputs(result: SimulationResult, input_name: str | None = None) -> list[Path]:
    """Write the four CSV files, report.html and run.json into a new ``output/run_NNN`` folder.

    Returns the six paths, CSVs first. ``input_name`` is the requests file the run
    came from (the CLI passes it); it is recorded in run.json so the comparison
    page can group runs of the same input.

    NNN is one more than the highest existing run number, so earlier runs are kept.
    """
    summary = compute_summary(result)
    num_elevators = len(result.elevator_stats)

    positions = [("time", *(f"elevator_{i}" for i in range(num_elevators)))]
    positions += [(t, *floors) for t, floors in result.positions]

    passengers = [PASSENGER_COLUMNS]
    passengers += [
        (p.id, p.request_time, p.source, p.dest, p.assigned_elevator,
         p.pickup_time, p.dropoff_time, p.wait_time, p.travel_time, p.total_time)
        for p in result.passengers
    ]

    run_facts = (summary.passenger_count, summary.final_time, summary.dispatcher_name,
                 _blank_if_none(summary.max_wait_passenger_id))
    stats_rows = [SUMMARY_COLUMNS]
    stats_rows += [
        (measure, *_stats_cells(stats), *run_facts)
        for measure, stats in (("wait", summary.wait), ("travel", summary.travel),
                               ("total", summary.total))
    ]

    elevators = [ELEVATOR_COLUMNS]
    elevators += [
        (e.elevator_id, e.served, e.moving_ticks, e.idle_ticks, e.stops, e.peak_load)
        for e in summary.elevators
    ]

    files = {
        POSITIONS_FILE: positions,
        PASSENGERS_FILE: passengers,
        SUMMARY_FILE: stats_rows,
        ELEVATORS_FILE: elevators,
    }
    report = build_report(result)  # built before the folder, so a failure leaves no empty run
    config = result.config
    run_info = {
        "input": input_name if input_name is not None else FROM_CODE,
        "floors": config.num_floors,
        "elevators": config.num_elevators,
        "capacity": config.capacity,
        "dispatcher": summary.dispatcher_name,
    }

    folder = _new_run_folder()
    paths = []
    for name, rows in files.items():
        path = folder / name
        _write_csv(path, rows)
        paths.append(path)
    report_path = folder / REPORT_FILE
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        f.write(report)
    paths.append(report_path)
    run_info_path = folder / RUN_INFO_FILE
    with open(run_info_path, "w", newline="", encoding="utf-8") as f:
        f.write(json.dumps(run_info, indent=2) + "\n")
    paths.append(run_info_path)
    return paths


def _new_run_folder() -> Path:
    """Create and return output/run_NNN, numbered one past the highest existing run."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    numbers = [
        int(match.group(1))
        for entry in OUTPUT_DIR.iterdir()
        if entry.is_dir() and (match := RUN_FOLDER.fullmatch(entry.name))
    ]
    folder = OUTPUT_DIR / f"run_{max(numbers, default=0) + 1:03d}"
    folder.mkdir()
    return folder


def _write_csv(path: Path, rows: Iterable[Iterable[object]]) -> None:
    """UTF-8 with \\n line endings, so output is byte-identical on every OS."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)


def _stats_cells(s: Stats) -> tuple[object, ...]:
    """min, max, mean, median, p95; mean and median to 2 decimals; blank when there are no values."""
    if s.min is None:
        return ("",) * 5
    return (s.min, s.max, f"{s.mean:.2f}", f"{s.median:.2f}", s.p95)


def _blank_if_none(value: object) -> object:
    return "" if value is None else value
