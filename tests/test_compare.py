"""The comparison page across runs (output/compare.html)."""

import json
import re
import shutil
from pathlib import Path

import pytest
from conftest import pdf_sample_result

from elevator_sim.cli import main
from elevator_sim.compare import build_comparison
from elevator_sim.output import write_outputs

SAMPLE = str(Path(__file__).parent.parent / "examples" / "sample.csv")
OUT = Path("output")


@pytest.fixture(autouse=True)
def _run_in_temp_folder(tmp_path, monkeypatch):
    """Run each test from an empty temp folder, so output/ is created there, not in the project."""
    monkeypatch.chdir(tmp_path)


def run_cli(input_path=SAMPLE, floors=100, elevators=2, capacity=10, dispatcher="nearest"):
    code = main(["--input", input_path, "--floors", str(floors), "--elevators", str(elevators),
                 "--capacity", str(capacity), "--dispatcher", dispatcher])
    assert code == 0


def small_input():
    path = Path("small.csv")
    path.write_text("time,id,source,dest\n0,a,1,8\n2,b,9,2\n4,c,3,10\n")
    return str(path)


def page():
    return (OUT / "compare.html").read_text(encoding="utf-8")


def embedded_data(text):
    match = re.search(r'<script type="application/json" id="compare-data">(.*?)</script>', text, re.S)
    return json.loads(match.group(1))


def test_run_json_records_input_and_settings():
    paths = write_outputs(pdf_sample_result(), input_name="examples/sample.csv")
    info = json.loads(paths[-1].read_text())
    fingerprint = info.pop("requests_fingerprint")
    assert re.fullmatch(r"[0-9a-f]{16}", fingerprint)
    assert info == {
        "input": "examples/sample.csv", "floors": 100, "elevators": 2, "capacity": 10,
        "dispatcher": "nearest",
    }


def test_same_requests_give_the_same_fingerprint_whatever_the_file():
    copy = Path("copy of sample.csv")
    copy.write_text("time , id , source , dest\n0,passenger1,1,51\n\n0,passenger2,1,37\n10,passenger3,20,1\n")
    run_cli(SAMPLE)
    run_cli(str(copy), dispatcher="eta")
    run_cli("./" + str(copy))
    fingerprints = {json.loads((OUT / f"run_00{i}" / "run.json").read_text())["requests_fingerprint"]
                    for i in (1, 2, 3)}
    assert len(fingerprints) == 1


def test_run_json_marks_runs_made_from_code():
    paths = write_outputs(pdf_sample_result())
    assert json.loads(paths[-1].read_text())["input"] == "(from code)"


def test_cli_writes_comparison_after_every_run():
    run_cli()
    assert (OUT / "compare.html").is_file()
    run_cli(dispatcher="eta")
    assert "run_002" in page()


def test_comparison_groups_runs_by_input_and_settings():
    run_cli(dispatcher="nearest")
    run_cli(dispatcher="eta")
    run_cli(small_input(), floors=10, elevators=2, capacity=4)
    text = page()
    assert text.count('<section class="group">') == 2
    assert f"{SAMPLE} · 100 floors · 2 elevators · capacity 10 · 3 passengers" in text
    assert "small.csv · 10 floors · 2 elevators · capacity 4 · 3 passengers" in text
    assert "3 runs in 2 groups." in text
    groups = embedded_data(text)
    assert [[r["label"] for r in g] for g in groups] == [
        ["run_001 · Nearest elevator (nearest)", "run_002 · Earliest arrival (eta)"],
        ["run_003 · Nearest elevator (nearest)"],
    ]
    assert groups[0][0]["waits"] == [0, 0, 71]
    assert groups[0][1]["waits"] == [0, 0, 43]
    assert groups[0][1]["totals"] == [50, 36, 62]


def test_same_passengers_from_differently_named_files_are_one_group():
    Path("renamed.csv").write_text(Path(SAMPLE).read_text())
    run_cli(SAMPLE)
    run_cli("renamed.csv", dispatcher="eta")
    run_cli("./renamed.csv")
    text = page()
    assert text.count('<section class="group">') == 1
    assert f"{SAMPLE}, renamed.csv, ./renamed.csv · 100 floors" in text


def test_same_file_name_with_edited_passengers_is_a_separate_group():
    path = Path("requests.csv")
    path.write_text("time,id,source,dest\n0,a,1,8\n")
    run_cli(str(path), floors=10)
    path.write_text("time,id,source,dest\n0,a,1,8\n3,b,9,2\n")
    run_cli(str(path), floors=10, dispatcher="eta")
    assert page().count('<section class="group">') == 2


def test_runs_made_before_fingerprints_group_by_input_path():
    for name in ("run_001", "run_002"):
        write_outputs(pdf_sample_result(), input_name="sample.csv")
        info_path = OUT / name / "run.json"
        info = json.loads(info_path.read_text())
        del info["requests_fingerprint"]
        info_path.write_text(json.dumps(info))
    assert build_comparison(OUT).count('<section class="group">') == 1


def test_comparison_table_shows_each_dispatcher_and_bolds_the_best():
    run_cli(dispatcher="nearest")
    run_cli(dispatcher="eta")
    text = page()
    nearest_row = re.search(r"<tr><td><a href=\"run_001/report.html\">run_001</a>.*?</tr>", text).group(0)
    eta_row = re.search(r"<tr><td><a href=\"run_002/report.html\">run_002</a>.*?</tr>", text).group(0)
    assert "<td>Nearest elevator (nearest)</td>" in nearest_row
    assert "<td>Earliest arrival (eta)</td>" in eta_row
    # ETA is better on final time (72 vs 100), wait mean (14.33 vs 23.67) and total p95 (62 vs 90).
    assert "<td><strong>72</strong></td>" in eta_row and "<td>100</td>" in nearest_row
    assert "<td><strong>14.33</strong></td>" in eta_row and "<td>23.67</td>" in nearest_row
    assert "<td><strong>62</strong></td>" in eta_row and "<td>90</td>" in nearest_row
    assert "<td>3 / 0</td>" in nearest_row and "<td>1 / 2</td>" in eta_row  # served per elevator


def test_charts_have_a_legend_and_served_column_names_each_elevator():
    run_cli(elevators=2)
    text = page()
    assert text.count('<div class="legend">') == 2  # one per chart
    for item in ("one passenger", "mean (average)", "p95 (95% of passengers at or below)"):
        assert item in text
    assert "<th>passengers served<br>by elevator 0 / 1</th>" in text


def test_runs_without_run_json_are_skipped_and_counted():
    run_cli()
    (OUT / "run_002").mkdir()  # e.g. a run made before comparisons existed
    assert "1 run in 1 group." in build_comparison(OUT)
    assert "1 folder was skipped" in build_comparison(OUT)


def test_deleted_run_disappears_from_the_comparison():
    run_cli()
    run_cli(dispatcher="eta")
    shutil.rmtree(OUT / "run_002")
    # The next run rebuilds the page. It is numbered one past the highest remaining
    # folder (run_001), so it reuses run_002, now a nearest run.
    run_cli()
    text = page()
    labels = [r["label"] for g in embedded_data(text) for r in g]
    assert labels == ["run_001 · Nearest elevator (nearest)", "run_002 · Nearest elevator (nearest)"]
    assert "Earliest arrival" not in text


def test_single_run_group_says_nothing_to_compare():
    run_cli()
    assert "Only one run so far." in page()


def test_no_runs_yet():
    assert "No runs to compare yet." in build_comparison(OUT)


def test_hostile_input_name_is_escaped():
    write_outputs(pdf_sample_result(), input_name='</script><script>alert(1)</script>{{GROUPS}}')
    text = build_comparison(OUT)
    assert "<script>alert(1)" not in text
    assert "&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;{{GROUPS}}" in text
    assert text.count("</script>") == 2  # only the page's own two script elements
    embedded_data(text)


def test_comparison_is_identical_when_rebuilt():
    run_cli()
    run_cli(dispatcher="eta")
    assert build_comparison(OUT) == build_comparison(OUT) == page()


def test_comparison_loads_nothing_from_the_internet():
    run_cli()
    text = page()
    assert not re.search(r'(src|href)\s*=\s*["\']?(https?:)?//', text)
    assert "@import" not in text
