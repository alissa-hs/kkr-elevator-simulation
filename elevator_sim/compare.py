"""Comparison page across runs: output/compare.html.

Rebuilt by the CLI after every run from the files in each output/run_NNN folder.
Runs are grouped by input file and building settings, so each group compares
dispatchers on the same passengers in the same building.
"""

from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from elevator_sim.dispatch import DISPATCHERS
from elevator_sim.output import (
    ELEVATORS_FILE,
    OUTPUT_DIR,
    PASSENGERS_FILE,
    RUN_FOLDER,
    RUN_INFO_FILE,
    SUMMARY_FILE,
)
from elevator_sim.report import REPORT_FILE

COMPARE_FILE = "compare.html"
TEMPLATE = "compare_template.html"
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")

# Metric columns: (header, measure row in summary.csv, column). Lower is better for all.
METRICS = [
    ("wait mean", "wait", "mean"),
    ("wait p95", "wait", "p95"),
    ("total mean", "total", "mean"),
    ("total p95", "total", "p95"),
]


LEGEND = (
    '<div class="legend">'
    '<span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="4" class="dot"/></svg>'
    "one passenger</span>"
    '<span><svg width="14" height="16" aria-hidden="true"><line x1="7" x2="7" y1="1" y2="15" class="mean"/></svg>'
    "mean (average)</span>"
    '<span><svg width="14" height="16" aria-hidden="true"><line x1="7" x2="7" y1="1" y2="15" class="p95"/></svg>'
    "p95 (95% of passengers at or below)</span>"
    "</div>"
)


@dataclass
class Run:
    folder: str
    number: int
    input: str
    floors: int
    elevators: int
    capacity: int
    dispatcher: str
    passengers: int
    final_time: int
    stats: dict[tuple[str, str], str]
    """(measure, column) -> cell text from summary.csv, e.g. ("wait", "mean") -> "23.67"."""
    longest_wait: str
    waits: list[int]
    totals: list[int]
    served: list[int]

    @property
    def group(self) -> tuple[str, int, int, int]:
        return (self.input, self.floors, self.elevators, self.capacity)


def write_comparison(output_dir: Path = OUTPUT_DIR) -> Path:
    """Rebuild compare.html from every run in ``output_dir`` and return its path."""
    path = output_dir / COMPARE_FILE
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write(build_comparison(output_dir))
    return path


def build_comparison(output_dir: Path = OUTPUT_DIR) -> str:
    runs, skipped = load_runs(output_dir)
    groups: dict[tuple, list[Run]] = {}
    for run in runs:  # runs are in run-number order, so groups appear in order of first run
        groups.setdefault(run.group, []).append(run)

    values = {
        "INTRO": _intro(runs, groups, skipped),
        "GROUPS": "".join(_group_section(i, g) for i, g in enumerate(groups.values())),
        "DATA_JSON": _data_json(list(groups.values())),
    }
    template = files("elevator_sim").joinpath(TEMPLATE).read_text(encoding="utf-8")
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def load_runs(output_dir: Path) -> tuple[list[Run], int]:
    """Every readable run folder, in run-number order, plus how many were skipped."""
    if not output_dir.is_dir():
        return [], 0
    folders = sorted(
        (int(m.group(1)), entry)
        for entry in output_dir.iterdir()
        if entry.is_dir() and (m := RUN_FOLDER.fullmatch(entry.name))
    )
    runs, skipped = [], 0
    for number, folder in folders:
        try:
            runs.append(_load_run(number, folder))
        except (OSError, ValueError, KeyError, IndexError):
            skipped += 1  # no run.json (made before comparisons existed) or unreadable
    return runs, skipped


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_run(number: int, folder: Path) -> Run:
    info = json.loads((folder / RUN_INFO_FILE).read_text(encoding="utf-8"))
    summary = _read_csv(folder / SUMMARY_FILE)
    passengers = _read_csv(folder / PASSENGERS_FILE)
    elevators = _read_csv(folder / ELEVATORS_FILE)
    first = summary[0]
    return Run(
        folder=folder.name,
        number=number,
        input=str(info["input"]),
        floors=int(info["floors"]),
        elevators=int(info["elevators"]),
        capacity=int(info["capacity"]),
        dispatcher=str(info["dispatcher"]),
        passengers=int(first["passengers"]),
        final_time=int(first["final_time"]),
        stats={(row["measure"], col): row[col] for row in summary for col in ("mean", "p95", "max")},
        longest_wait=first["longest_wait_passenger"],
        waits=[int(p["wait_time"]) for p in passengers],
        totals=[int(p["total_time"]) for p in passengers],
        served=[int(e["served"]) for e in elevators],
    )


def _intro(runs: list[Run], groups: dict, skipped: int) -> str:
    if not runs:
        text = "No runs to compare yet. Each CLI run adds one."
    else:
        text = (f"{len(runs)} run{'s' if len(runs) != 1 else ''} in "
                f"{len(groups)} group{'s' if len(groups) != 1 else ''}. "
                "Each group is one input file in one building, so the only difference "
                "between its runs is the dispatcher.")
    if skipped:
        text += (f" {skipped} folder{'s were' if skipped != 1 else ' was'} skipped "
                 "(no run.json, e.g. made by an older version).")
    return html.escape(text)


def _dispatcher_label(name: str) -> str:
    cls = DISPATCHERS.get(name)
    return f"{cls.label} ({name})" if cls and cls.label else name


def _number(text: str) -> float | None:
    try:
        return float(text)
    except ValueError:
        return None  # blank cell: no passengers


def _group_section(index: int, runs: list[Run]) -> str:
    first = runs[0]
    title = (f"{first.input} · {first.floors} floors · {first.elevators} elevators · "
             f"capacity {first.capacity} · {first.passengers} passengers")

    # Lowest value per metric (and final time) within the group, so it can be bolded.
    best: dict[str, float] = {}
    for header, measure, col in METRICS:
        nums = [n for r in runs if (n := _number(r.stats[(measure, col)])) is not None]
        if nums:
            best[header] = min(nums)
    best["final time"] = min(r.final_time for r in runs)

    def cell(header: str, text: str, value: float | None) -> str:
        shown = html.escape(text if text else "—")
        if value is not None and len(runs) > 1 and value == best.get(header):
            return f"<td><strong>{shown}</strong></td>"
        return f"<td>{shown}</td>"

    order = (" / ".join(str(i) for i in range(first.elevators)) if first.elevators <= 6
             else f"0 to {first.elevators - 1}, in order")
    head = ["Run", "Dispatcher", "final time", *[h for h, _, _ in METRICS], "longest wait"]
    # Two-line header: "passengers served" / "by elevator 0 / 1 / 2".
    served_th = f"<th>passengers served<br>by elevator {html.escape(order)}</th>"
    body = []
    for r in runs:
        cells = [
            f'<td><a href="{r.folder}/{REPORT_FILE}">{html.escape(r.folder)}</a></td>',
            f"<td>{html.escape(_dispatcher_label(r.dispatcher))}</td>",
            cell("final time", str(r.final_time), r.final_time),
            *[cell(h, r.stats[(m, c)], _number(r.stats[(m, c)])) for h, m, c in METRICS],
            f"<td>{html.escape(r.longest_wait or '—')} ({html.escape(r.stats[('wait', 'max')] or '—')})</td>",
            f"<td>{html.escape(' / '.join(map(str, r.served)))}</td>",
        ]
        body.append("<tr>" + "".join(cells) + "</tr>")
    table = ("<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in head)
             + served_th + "</tr></thead><tbody>" + "".join(body) + "</tbody></table>")

    note = ("" if len(runs) > 1 else
            '<p class="note" style="margin:8px 0 0">Only one run so far. Run the same input '
            "with another <code>--dispatcher</code> to compare.</p>")
    return (
        f'<section class="group"><h2>{html.escape(title)}</h2>'
        f'<div class="panel">{table}{note}</div>'
        f'<h3>Total time per passenger (request to dropoff)</h3>'
        f'<div class="panel">{LEGEND}<svg class="strip" data-group="{index}" data-measure="totals" '
        f'role="img" aria-label="Total time per passenger, one row per run"></svg></div>'
        f'<h3>Wait per passenger (request to pickup)</h3>'
        f'<div class="panel">{LEGEND}<svg class="strip" data-group="{index}" data-measure="waits" '
        f'role="img" aria-label="Wait per passenger, one row per run"></svg></div>'
        f"</section>"
    )


def _data_json(groups: list[list[Run]]) -> str:
    """Per-run values for the charts, safe to place inside a <script> element."""
    data = [
        [
            {
                "label": f"{r.folder} · {_dispatcher_label(r.dispatcher)}",
                "waits": r.waits,
                "totals": r.totals,
                "waitsMean": _number(r.stats[("wait", "mean")]),
                "waitsP95": _number(r.stats[("wait", "p95")]),
                "totalsMean": _number(r.stats[("total", "mean")]),
                "totalsP95": _number(r.stats[("total", "p95")]),
            }
            for r in runs
        ]
        for runs in groups
    ]
    text = json.dumps(data, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
