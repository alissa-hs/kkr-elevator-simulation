"""The HTML report."""

import json
import re
from importlib.resources import files

from conftest import pdf_sample_result, req, run_sim

from elevator_sim.report import TEMPLATE, build_report


def embedded_data(page):
    match = re.search(r'<script type="application/json" id="run-data">(.*?)</script>', page, re.S)
    return json.loads(match.group(1))


def test_report_contains_the_run_data():
    page = build_report(pdf_sample_result())
    data = embedded_data(page)
    assert data["floors"] == 100
    assert data["finalTime"] == 100
    assert len(data["positions"]) == 2
    assert data["positions"][0][:3] == [1, 2, 3]
    assert data["positions"][1] == [1] * 101
    assert data["totals"] == [50, 36, 90]
    assert data["rides"] == [[0, 0, 50], [0, 0, 36], [0, 81, 100]]
    assert data["totalP95"] == 90


def test_report_shows_run_info_and_tables():
    page = build_report(pdf_sample_result())
    assert "100 floors · 2 elevators · capacity 10 · 3 passengers · final time 100" in page
    assert "<td>Wait</td><td>0</td><td>71</td><td>23.67</td><td>0.00</td><td>71</td>" in page
    assert "Longest wait: passenger3 (71 ticks)" in page
    assert "<td>1</td><td>0</td><td>0</td><td>101</td><td>0</td><td>0</td>" in page


def test_report_highlights_dispatch_and_routing_methods():
    page = build_report(pdf_sample_result())
    assert '<div class="algo-kind">Dispatch</div><div class="algo-name">Nearest elevator (nearest)</div>' in page
    assert "Each new request goes to the elevator closest to the passenger&#x27;s floor" in page
    assert '<div class="algo-kind">Routing</div><div class="algo-name">LOOK</div>' in page
    assert "reverses only when nothing is left ahead" in page


def test_report_lists_every_passenger():
    page = build_report(pdf_sample_result())
    assert ("<th>time</th><th>id</th><th>source</th><th>dest</th><th>elevator</th><th>pickup</th>"
            "<th>dropoff</th><th>wait</th><th>travel</th><th>total</th>") in page
    assert "<td>0</td><td>passenger1</td><td>1</td><td>51</td><td>0</td><td>0</td>" in page
    assert ("<td>10</td><td>passenger3</td><td>20</td><td>1</td><td>0</td><td>81</td>"
            "<td>100</td><td>71</td><td>19</td><td>90</td>") in page


def test_report_shows_worst_case_total_time_and_how_close_the_run_came():
    page = build_report(pdf_sample_result())
    # 2 × 100 floors × (3 passengers + 1) = 800; longest total time 90 = 11.25%.
    assert ("Calculated worst-case total wait time (request to dropoff): 800 ticks, "
            "from 2 × floors × (passengers + 1) = 2 × 100 × (3 + 1). "
            "The longest actual total time, 90 ticks, is 11.2% of it.") in page


def test_empty_run_worst_case_has_nothing_to_compare():
    result, _ = run_sim([], num_elevators=2)
    assert ("Calculated worst-case total wait time (request to dropoff): 20 ticks, "
            "from 2 × floors × (passengers + 1) = 2 × 10 × (0 + 1). "
            "No passengers, so nothing to compare.") in build_report(result)


def test_every_placeholder_is_filled():
    assert "{{" not in build_report(pdf_sample_result())


def test_hostile_passenger_id_is_escaped():
    hostile = '</script><script>alert(1)</script>{{DATA_JSON}}&'
    result, _ = run_sim([req(0, hostile, 1, 5)])
    page = build_report(result)
    assert "<script>alert(1)" not in page
    assert "&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.count("</script>") == 2  # only the page's own two script elements
    # The id's {{DATA_JSON}} is shown as text (longest wait + passengers table), not filled in.
    assert page.count("{{DATA_JSON}}") == 2
    embedded_data(page)  # the data block still parses


def test_report_is_identical_across_runs():
    assert build_report(pdf_sample_result()) == build_report(pdf_sample_result())


def test_empty_run_report_says_no_passengers():
    result, _ = run_sim([], num_elevators=2)
    page = build_report(result)
    assert embedded_data(page)["totals"] == []
    assert "No passengers in this run" in page
    assert "Longest wait: —" in page


def test_report_loads_nothing_from_the_internet():
    page = build_report(pdf_sample_result())
    assert not re.search(r'(src|href)\s*=\s*["\']?(https?:)?//', page)
    assert "@import" not in page
    assert not re.search(r"url\(\s*['\"]?(https?:)?//", page)


def test_template_is_packaged():
    assert files("elevator_sim").joinpath(TEMPLATE).is_file()
