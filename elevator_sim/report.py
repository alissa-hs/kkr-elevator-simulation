"""Self-contained HTML report for a finished run (written by output.write_outputs).

The page is one file with no external resources: tables are rendered here,
and the run's data is embedded as JSON for the charts and playback, which the
template draws with plain JavaScript and SVG.
"""

from __future__ import annotations

import html
import json
import re
from importlib.resources import files

from elevator_sim.dispatch import DISPATCHERS
from elevator_sim.metrics import Stats, Summary, compute_summary
from elevator_sim.routing import ROUTING_DESCRIPTION, ROUTING_NAME
from elevator_sim.simulation import SimulationResult, starvation_limit

REPORT_FILE = "report.html"
TEMPLATE = "report_template.html"
PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def build_report(result: SimulationResult) -> str:
    """The full HTML page as a string. Same result in, same text out."""
    summary = compute_summary(result)
    values = {
        "RUN_INFO": _run_info(result, summary),
        "ALGORITHMS": _algorithms(summary),
        "METRICS_TABLE": _metrics_table(summary),
        "LONGEST_WAIT": _longest_wait(summary),
        "WORST_CASE": _worst_case(result, summary),
        "ELEVATORS_TABLE": _elevators_table(summary),
        "PASSENGERS_TABLE": _passengers_table(result),
        "DATA_JSON": _data_json(result, summary),
    }
    template = files("elevator_sim").joinpath(TEMPLATE).read_text(encoding="utf-8")
    # One pass, so text inserted for one placeholder is never scanned for another.
    return PLACEHOLDER.sub(lambda m: values[m.group(1)], template)


def _run_info(result: SimulationResult, summary: Summary) -> str:
    c = result.config
    parts = [
        f"{c.num_floors} floors",
        f"{c.num_elevators} elevator{'s' if c.num_elevators != 1 else ''}",
        f"capacity {c.capacity}",
        f"{summary.passenger_count} passenger{'s' if summary.passenger_count != 1 else ''}",
        f"final time {summary.final_time}",
    ]
    return html.escape(" · ".join(parts))


def _algorithms(summary: Summary) -> str:
    """The dispatch and routing methods, side by side, with a sentence on each."""
    dispatcher = DISPATCHERS.get(summary.dispatcher_name)
    dispatch_label = (dispatcher.label if dispatcher and dispatcher.label
                      else summary.dispatcher_name)
    dispatch_text = dispatcher.description if dispatcher else ""
    cards = [
        ("Dispatch", f"{dispatch_label} ({summary.dispatcher_name})", dispatch_text),
        ("Routing", ROUTING_NAME, ROUTING_DESCRIPTION),
    ]
    return "".join(
        f'<div class="algo"><div class="algo-kind">{html.escape(kind)}</div>'
        f'<div class="algo-name">{html.escape(name)}</div>'
        f'<p class="algo-text">{html.escape(text.strip())}</p></div>'
        for kind, name, text in cards
    )


def _stats_cells(s: Stats) -> list[str]:
    if s.min is None:
        return ["—"] * 5
    return [str(s.min), str(s.max), f"{s.mean:.2f}", f"{s.median:.2f}", str(s.p95)]


def _table(header: list[str], rows: list[list[str]], css_class: str = "") -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    class_attr = f' class="{css_class}"' if css_class else ""
    return f"<table{class_attr}><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _metrics_table(summary: Summary) -> str:
    rows = [
        [label, *_stats_cells(s)]
        for label, s in (("Wait", summary.wait), ("Travel", summary.travel),
                         ("Total", summary.total))
    ]
    return _table(["Ticks", "min", "max", "mean", "median", "p95"], rows)


def _longest_wait(summary: Summary) -> str:
    if summary.max_wait_passenger_id is None:
        return "Longest wait: —"
    return html.escape(
        f"Longest wait: {summary.max_wait_passenger_id} ({summary.wait.max} ticks)"
    )


def _worst_case(result: SimulationResult, summary: Summary) -> str:
    """The starvation limit with its formula, filled in, and how close this run came to it."""
    floors, count = result.config.num_floors, summary.passenger_count
    limit = starvation_limit(floors, count)
    text = (f"Calculated worst-case total wait time (request to dropoff): {limit:,} ticks, "
            f"from 2 × floors × (passengers + 1) = 2 × {floors} × ({count} + 1). ")
    if summary.total.max is None:
        return html.escape(text + "No passengers, so nothing to compare.")
    share = 100 * summary.total.max / limit
    return html.escape(
        text + f"The longest actual total time, {summary.total.max} ticks, is {share:.1f}% of it."
    )


def _elevators_table(summary: Summary) -> str:
    rows = [
        [str(e.elevator_id), str(e.served), str(e.moving_ticks), str(e.idle_ticks),
         str(e.stops), str(e.peak_load)]
        for e in summary.elevators
    ]
    return _table(["Elevator", "served", "moving ticks", "idle ticks", "stops", "peak load"], rows)


def _passengers_table(result: SimulationResult) -> str:
    """Every passenger, earliest request first: the request, then what happened."""
    if not result.passengers:
        return '<p class="note">No passengers in this run.</p>'
    rows = [
        [str(p.request_time), p.id, str(p.source), str(p.dest), str(p.assigned_elevator),
         str(p.pickup_time), str(p.dropoff_time), str(p.wait_time), str(p.travel_time),
         str(p.total_time)]
        for p in result.passengers
    ]
    return _table(
        ["time", "id", "source", "dest", "elevator", "pickup", "dropoff", "wait", "travel", "total"],
        rows,
        css_class="passengers",
    )


def _data_json(result: SimulationResult, summary: Summary) -> str:
    """Run data for the charts, safe to place inside a <script> element."""
    num_elevators = len(result.elevator_stats)
    data = {
        "floors": result.config.num_floors,
        "finalTime": result.final_time,
        "positions": [[floors[i] for _, floors in result.positions] for i in range(num_elevators)],
        "rides": [[p.assigned_elevator, p.pickup_time, p.dropoff_time] for p in result.passengers],
        "totals": [p.total_time for p in result.passengers],
        "totalMean": summary.total.mean,
        "totalP95": summary.total.p95,
    }
    text = json.dumps(data, separators=(",", ":"))
    # Escape characters that could end the <script> element or start markup early.
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
