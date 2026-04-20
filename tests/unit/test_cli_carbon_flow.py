from pathlib import Path
from types import SimpleNamespace

from green_code_smell import cli


class _DummyTracker:
    def __init__(self, emissions=0.001, energy=0.002):
        self.final_emissions_data = SimpleNamespace(
            emissions=emissions,
            energy_consumed=energy,
            cpu_power=1.0,
            ram_power=2.0,
            cpu_energy=3.0,
            ram_energy=4.0,
            emissions_rate=0.5,
            region="x",
            country_name="y",
        )

    def start(self):
        return None

    def stop(self):
        return 1.2


def test_run_entry_point_with_carbon_success_and_timeout(monkeypatch, tmp_path: Path):
    target = tmp_path / "prog.py"
    target.write_text("print('ok')\n", encoding="utf-8")

    calls = {"n": 0}

    def fake_tracker(*args, **kwargs):
        return _DummyTracker()

    class _Timeout(Exception):
        pass

    def fake_run(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(stdout="ok", stderr="", returncode=0)
        raise cli.subprocess.TimeoutExpired(cmd="x", timeout=1)

    monkeypatch.setattr(cli, "EmissionsTracker", fake_tracker)
    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    runs, result, duration = cli.run_entry_point_with_carbon(target, iterations=2, timeout=1)
    assert len(runs) == 1
    assert result.returncode == 0
    assert duration == 1.2


def test_compute_average_run_data_and_print_output(capsys):
    stats = cli.compute_average_run_data(
        [
            {"emission": 2.0, "energy_consumed": 4.0, "emissions_rate": 6.0, "region": "a", "country_name": "b"},
            {"emission": 4.0, "energy_consumed": 8.0, "emissions_rate": 10.0, "region": "a", "country_name": "b"},
        ]
    )
    assert stats["avg_emission"] == 3.0
    assert cli.compute_average_run_data([]) is None

    cli._print_program_output(SimpleNamespace(stdout="hello", stderr="warn", returncode=3))
    output = capsys.readouterr().out
    assert "Program output" in output
    assert "Program exited with code 3" in output


def test_process_carbon_runs_happy_path(monkeypatch):
    monkeypatch.setattr(cli, "calculate_cosmic_cfp", lambda _: 2)
    monkeypatch.setattr(cli, "display_carbon_report", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "impact_analysis", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        cli,
        "save_metric_to_history",
        lambda *args, **kwargs: ([{"id": 1, "emission_kg": 0.1, "smell_breakdown": {}}], False),
    )
    ok = cli._process_carbon_runs(
        Path("main.py"),
        [{"emission": 1.0, "energy_consumed": 2.0, "emissions_rate": 3.0, "region": "r", "country_name": "c"}],
        SimpleNamespace(stdout="", stderr="", returncode=0),
        1.0,
        5,
        {"DeadCode": {"count": 1, "loc": 1}},
    )
    assert ok is True


def test_process_carbon_runs_no_data_returns_false():
    assert cli._process_carbon_runs(Path("x.py"), [], None, 1, 1) is False


def test_carbon_track_branches(monkeypatch, tmp_path: Path):
    args = SimpleNamespace(no_carbon=False, carbon_run=None)
    monkeypatch.setattr(cli, "CODECARBON_AVAILABLE", True)
    monkeypatch.setattr(cli, "_resolve_carbon_target_file", lambda p, a: tmp_path / "app.py")
    monkeypatch.setattr(
        cli,
        "run_entry_point_with_carbon",
        lambda *a, **k: ([{"emission": 1.0, "energy_consumed": 2.0, "emissions_rate": 3.0, "region": "r", "country_name": "c"}], SimpleNamespace(stdout="", stderr="", returncode=0), 1.0),
    )
    monkeypatch.setattr(cli, "_print_program_output", lambda *a, **k: None)
    monkeypatch.setattr(cli, "_process_carbon_runs", lambda *a, **k: True)
    cli.carbon_track(".", args, total_loc=2, smell_breakdown={})

    # Early returns
    args2 = SimpleNamespace(no_carbon=True, carbon_run=None)
    cli.carbon_track(".", args2)
    monkeypatch.setattr(cli, "_resolve_carbon_target_file", lambda p, a: None)
    cli.carbon_track(".", args)
