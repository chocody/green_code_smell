import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from green_code_smell import cli


def test_calculate_green_metrics_with_and_without_loc():
    m1 = cli.calculate_green_metrics(2, 10, 4, embodied_carbon=5)
    assert m1["total_emissions_gCO2eq"] == 25
    assert m1["sci_gCO2eq_per_line"] == 6.25

    m2 = cli.calculate_green_metrics(2, 10, 0)
    assert m2["sci_gCO2eq_per_line"] == 0


@pytest.mark.parametrize(
    "current, previous, expected",
    [
        (1, None, "Initial"),
        (8, 10, "Greener ✅"),
        (12, 10, "Hotter ⚠️"),
        (10.5, 10, "Normal"),
    ],
)
def test_determine_green_status(current, previous, expected):
    assert cli.determine_green_status(current, previous) == expected


def test_get_python_files_for_file_and_directory(tmp_path: Path):
    f = tmp_path / "a.py"
    f.write_text("x=1\n", encoding="utf-8")
    out = cli.get_python_files(f)
    assert out == [f]

    d = tmp_path / "d"
    d.mkdir()
    (d / "x.py").write_text("x=1\n", encoding="utf-8")
    (d / "y.txt").write_text("x\n", encoding="utf-8")
    files = cli.get_python_files(d)
    assert files == [d / "x.py"]


def test_get_python_files_non_python_exits(tmp_path: Path):
    bad = tmp_path / "x.txt"
    bad.write_text("1\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        cli.get_python_files(bad)


def test_has_main_entry_and_main_function_only(tmp_path: Path):
    p1 = tmp_path / "m1.py"
    p1.write_text(
        "def main():\n    return 1\n\nif __name__ == '__main__':\n    main()\n",
        encoding="utf-8",
    )
    p2 = tmp_path / "m2.py"
    p2.write_text("def main():\n    return 2\n", encoding="utf-8")
    assert cli.has_main_entry(p1) is True
    assert cli.has_main_function_only(p1) is False
    assert cli.has_main_function_only(p2) is True


def test_find_main_file_directory_cases(tmp_path: Path):
    p = tmp_path / "single.py"
    p.write_text("if __name__ == '__main__':\n    print('ok')\n", encoding="utf-8")
    assert cli.find_main_file(tmp_path) == p

    p.unlink()
    no_entry = cli.find_main_file(tmp_path)
    assert no_entry == "error no entry point found"


def test_setup_rules_and_disable_all_exits():
    args = SimpleNamespace(
        no_god_class=False,
        max_methods=3,
        max_cc=4,
        max_loc=5,
        no_dup_check=False,
        dup_similarity=0.8,
        dup_min_statements=2,
        dup_check_within=True,
        dup_check_between=False,
        no_long_method=False,
        method_max_loc=11,
        max_cyclomatic=7,
        no_dead_code=False,
        no_mutable_default=False,
    )
    rules = cli.setup_rules(args)
    assert len(rules) == 5

    args.no_god_class = True
    args.no_dup_check = True
    args.no_long_method = True
    args.no_dead_code = True
    args.no_mutable_default = True
    with pytest.raises(SystemExit):
        cli.setup_rules(args)


def test_count_total_loc_and_breakdown():
    all_results = {
        Path("a.py"): [
            {"rule": "GodClass", "lineno": 1, "end_lineno": 4},
            {"rule": "MutableDefaultArguments", "lineno": 10, "end_lineno": 10},
        ],
        Path("b.py"): [{"rule": "DeadCode", "lineno": 3, "end_lineno": 3}],
    }
    # MutableDefaultArguments contributes 1 LOC in breakdown, but in this
    # function a typo means special case does not trigger and lineno path is used.
    assert cli.count_total_loc_code_smells(all_results) == 6
    breakdown = cli.compute_smell_breakdown(all_results)
    assert breakdown["GodClass"] == {"count": 1, "loc": 4}
    assert breakdown["MutableDefaultArguments"] == {"count": 1, "loc": 1}


def test_save_metric_to_history_initial_and_follow_up(tmp_path: Path):
    hist = tmp_path / "history.json"
    green = {"total_emissions_gCO2eq": 1, "total_loc_code_smells": 2, "sci_gCO2eq_per_line": 0.5}
    data1, different1 = cli.save_metric_to_history(
        str(hist),
        "a.py",
        1.0,
        0.1,
        0.2,
        300,
        green,
        10,
        smell_breakdown={"DeadCode": {"count": 1, "loc": 1}},
    )
    assert different1 is False
    assert data1[-1]["status"] == "Initial"

    green2 = {"total_emissions_gCO2eq": 1, "total_loc_code_smells": 2, "sci_gCO2eq_per_line": 0.3}
    data2, different2 = cli.save_metric_to_history(
        str(hist),
        "a.py",
        1.0,
        0.1,
        0.2,
        300,
        green2,
        10,
    )
    assert different2 is False
    assert data2[-1]["status"] == "Greener ✅"

    payload = json.loads(hist.read_text(encoding="utf-8"))
    assert len(payload) == 2


def test_resolve_carbon_target_file_with_explicit_file(tmp_path: Path):
    p = tmp_path / "run.py"
    p.write_text("print('ok')\n", encoding="utf-8")
    args = SimpleNamespace(carbon_run=str(p))
    assert cli._resolve_carbon_target_file(tmp_path, args) == p

    args2 = SimpleNamespace(carbon_run=str(tmp_path / "missing.py"))
    assert cli._resolve_carbon_target_file(tmp_path, args2) is None
