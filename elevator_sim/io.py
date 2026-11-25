"""Reading requests from CSV and checking them."""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Sequence
from os import PathLike

from elevator_sim.config import SimConfig
from elevator_sim.errors import InputError
from elevator_sim.models import Request

HEADER = ("time", "id", "source", "dest")
WHOLE_NUMBER = re.compile(r"-?[0-9]+")


def _row_rule_problems(r: Request, id_counts: Counter[str]) -> list[str]:
    """Validate row inputs"""
    problems = []
    if r.time < 0:
        problems.append(f"{r.label}: time {r.time} is negative")
    if r.source == r.dest:
        problems.append(f"{r.label}: source and dest are both floor {r.source}")
    if id_counts[r.passenger_id] > 1:
        problems.append(f"{r.label}: duplicate id '{r.passenger_id}'")
    return problems


def load_requests_csv(path: str | PathLike[str]) -> list[Request]:
    """Read requests from a CSV file with the header ``time,id,source,dest``.

    Spaces around fields are ignored and blank lines are skipped. Each request
    gets its physical ``line`` (header = line 1) and an ``input_order`` counting
    data rows only. Raises one InputError listing every bad row, in line order.
    Floor range checked in ``validate_requests``.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(_numbered_rows(csv.reader(f)))
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc

    if not rows:
        raise InputError(f"file is empty; expected header {','.join(HEADER)}")
    _, header = rows[0]
    if tuple(header) != HEADER:
        raise InputError(
            f"line 1: header must be {','.join(HEADER)}, got '{','.join(header)}'"
        )

    data = [(line, row) for line, row in rows[1:] if any(row)]
    id_counts = Counter(row[1] for _, row in data if len(row) == len(HEADER))
    problems: list[tuple[int, str]] = []
    requests: list[Request] = []

    for order, (line, row) in enumerate(data):
        if len(row) != len(HEADER):
            problems.append((line, f"line {line}: expected 4 fields, got {len(row)}"))
            continue
        time, pid, source, dest = row
        row_problems = [
            f"line {line}: {name} '{value}' is not a whole number"
            for name, value in (("time", time), ("source", source), ("dest", dest))
            if not WHOLE_NUMBER.fullmatch(value)
        ]
        if not pid:
            row_problems.append(f"line {line}: id is empty")
        if row_problems:
            problems.extend((line, p) for p in row_problems)
            continue
        request = Request(int(time), pid, int(source), int(dest), input_order=order, line=line)
        problems.extend((line, p) for p in _row_rule_problems(request, id_counts))
        requests.append(request)

    if problems:
        raise InputError("\n".join(p for _, p in sorted(problems, key=lambda lp: lp[0])))
    return requests


def _numbered_rows(reader):
    """Yield (physical line, stripped fields) for every row, including blank ones."""
    for row in reader:
        yield reader.line_num, [field.strip() for field in row]


def validate_requests(requests: Sequence[Request], config: SimConfig) -> None:
    """Validate every request against the row rules and the building's floor range.

    Error messages are added with line number and reason for each line.
    """
    problems: list[str] = []
    id_counts = Counter(r.passenger_id for r in requests)
    highest_bad_floor: int | None = None

    for r in requests:
        problems.extend(_row_rule_problems(r, id_counts))
        for floor in dict.fromkeys((r.source, r.dest)):  # each distinct floor once, in order
            if floor < 1:
                problems.append(f"{r.label}: floor {floor} is below 1")
            elif floor > config.num_floors:
                problems.append(f"{r.label}: floor {floor} is above --floors {config.num_floors}")
                highest_bad_floor = max(floor, highest_bad_floor or floor)

    if highest_bad_floor is not None:
        problems.append(f"use --floors {highest_bad_floor} or higher")
    if problems:
        raise InputError("\n".join(problems))
