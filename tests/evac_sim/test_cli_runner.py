from pathlib import Path

from evac_sim.cli import build_parser
from evac_sim import runner


def test_cli_parses_horizon_k_for_h2():
    parser = build_parser()

    args = parser.parse_args(
        [
            "run",
            "--config", "study.yaml",
            "--case", "demo_case",
            "--heuristic", "h2",
            "--beta", "2.5",
            "--horizon-k", "5",
        ]
    )

    assert args.cmd == "run"
    assert args.heuristic == "h2"
    assert args.beta == 2.5
    assert args.horizon_k == 5


def test_run_from_yaml_propagates_horizon_k(monkeypatch, tmp_path):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()

    (config_dir / "study.yaml").write_text(
        """
demo_case:
  environment: "dummy"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setattr(runner, "select_cases", lambda cases, case_id, environment: {"demo_case": {"environment": "dummy"}})
    monkeypatch.setattr(runner, "deep_merge", lambda defaults, case_cfg: case_cfg)

    class DummyPaths:
        project_root = tmp_path
        config_file = config_dir / "study.yaml"
        run_dir = tmp_path / "run"
        db_dir = tmp_path / "run" / "db"
        csv_dir = tmp_path / "run" / "csv"
        images_dir = tmp_path / "run" / "images"

    dummy_paths = DummyPaths()
    dummy_paths.run_dir.mkdir(parents=True, exist_ok=True)
    dummy_paths.db_dir.mkdir(parents=True, exist_ok=True)
    dummy_paths.csv_dir.mkdir(parents=True, exist_ok=True)
    dummy_paths.images_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(runner, "prepare_paths", lambda *args, **kwargs: dummy_paths)
    monkeypatch.setattr(runner, "setup_run_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "git_commit_hash", lambda *args, **kwargs: "abc123")

    captured = {}

    def fake_run_experiment_from_case(cfg, paths, case_id, heuristic="none", beta=1.0, horizon_k=None, **kwargs):
        captured["cfg"] = cfg
        captured["case_id"] = case_id
        captured["heuristic"] = heuristic
        captured["beta"] = beta
        captured["horizon_k"] = horizon_k

    monkeypatch.setattr(runner, "run_experiment_from_case", fake_run_experiment_from_case)

    runner.run_from_yaml(
        project_root=Path(tmp_path),
        config_name="study.yaml",
        case_id="demo_case",
        verbose=False,
        heuristic="h2",
        beta=2.0,
        horizon_k=4,
    )

    assert captured["case_id"] == "demo_case"
    assert captured["heuristic"] == "h2"
    assert captured["beta"] == 2.0
    assert captured["horizon_k"] == 4