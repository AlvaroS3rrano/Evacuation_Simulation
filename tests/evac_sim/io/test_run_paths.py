from pathlib import Path

import pytest

from evac_sim.io.run_paths import make_run_dir, prepare_case_paths, prepare_paths


def test_make_run_dir_creates_directory_inside_runs(tmp_path: Path):
    run_dir = make_run_dir(tmp_path, "case1", None)

    assert run_dir.exists()
    assert run_dir.is_dir()
    assert run_dir.parent == tmp_path / "runs"
    assert "case1" in run_dir.name


def test_make_run_dir_uses_out_dir_when_empty(tmp_path: Path):
    out_dir = tmp_path / "custom_out"

    run_dir = make_run_dir(tmp_path, "case1", out_dir)

    assert run_dir == out_dir
    assert out_dir.exists()
    assert out_dir.is_dir()


def test_make_run_dir_raises_if_out_dir_is_not_empty(tmp_path: Path):
    out_dir = tmp_path / "custom_out"
    out_dir.mkdir()
    (out_dir / "file.txt").write_text("content")

    with pytest.raises(FileExistsError):
        make_run_dir(tmp_path, "case1", out_dir)


def test_prepare_paths_creates_expected_subdirectories(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("test: true")

    paths = prepare_paths(
        project_root=tmp_path,
        config_file=config_file,
        case_id="demo_case",
        out_dir=tmp_path / "run_output",
    )

    assert paths.run_dir.exists()
    assert paths.logs_dir.exists()
    assert paths.artifacts_dir.exists()
    assert paths.images_dir.exists()
    assert paths.db_dir.exists()
    assert paths.csv_dir.exists()


def test_prepare_case_paths_sanitizes_case_id(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("test: true")
    cases_dir = tmp_path / "cases"

    paths = prepare_case_paths(
        project_root=tmp_path,
        config_file=config_file,
        case_id="case 01 / test",
        cases_dir=cases_dir,
    )

    assert paths.run_dir.parent == cases_dir
    assert paths.run_dir.name == "case_01___test"
    assert paths.logs_dir.exists()
    assert paths.artifacts_dir.exists()
    assert paths.images_dir.exists()
    assert paths.db_dir.exists()
    assert paths.csv_dir.exists()