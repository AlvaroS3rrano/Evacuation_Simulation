from pathlib import Path
from textwrap import dedent

import pytest

from evac_sim.io.config_loader import deep_merge, load_case, select_cases


def test_select_cases_without_filters_returns_all():
    cases = {
        "case1": {"environment": "indoor", "agents": 10},
        "case2": {"environment": "outdoor", "agents": 20},
    }

    selected = select_cases(cases)

    assert selected == cases


def test_select_cases_filters_by_case_id():
    cases = {
        "case1": {"environment": "indoor"},
        "case2": {"environment": "outdoor"},
    }

    selected = select_cases(cases, case_id="case1")

    assert selected == {"case1": {"environment": "indoor"}}


def test_select_cases_filters_by_environment():
    cases = {
        "case1": {"environment": "indoor"},
        "case2": {"environment": "outdoor"},
        "case3": {"environment": "indoor"},
    }

    selected = select_cases(cases, environment="indoor")

    assert selected == {
        "case1": {"environment": "indoor"},
        "case3": {"environment": "indoor"},
    }


def test_select_cases_filters_by_case_id_and_environment():
    cases = {
        "case1": {"environment": "indoor"},
        "case2": {"environment": "outdoor"},
        "case3": {"environment": "indoor"},
    }

    selected = select_cases(cases, case_id="case3", environment="indoor")

    assert selected == {"case3": {"environment": "indoor"}}


def test_select_cases_returns_empty_dict_when_no_case_matches():
    cases = {
        "case1": {"environment": "indoor"},
        "case2": {"environment": "outdoor"},
    }

    selected = select_cases(cases, case_id="case3")

    assert selected == {}


def test_load_case_returns_case_config(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        dedent(
            """
            case1:
              environment: indoor
              agents: 10
            case2:
              environment: outdoor
              agents: 20
            """
        ).strip(),
        encoding="utf-8",
    )

    cfg = load_case(config_file, "case1")

    assert cfg == {"environment": "indoor", "agents": 10}


def test_load_case_raises_key_error_when_case_does_not_exist(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
            case1:
              environment: indoor
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(KeyError, match="case_id 'case2' not found"):
        load_case(config_file, "case2")


def test_load_case_raises_type_error_when_case_is_not_a_dict(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
            case1: 123
        """.strip(),
        encoding="utf-8",
    )

    with pytest.raises(TypeError, match="must be a mapping/dict"):
        load_case(config_file, "case1")


def test_deep_merge_merges_nested_dicts():
    base = {
        "simulation": {
            "steps": 100,
            "seed": 42,
        },
        "environment": "indoor",
    }
    override = {
        "simulation": {
            "steps": 200,
        }
    }

    result = deep_merge(base, override)

    assert result == {
        "simulation": {
            "steps": 200,
            "seed": 42,
        },
        "environment": "indoor",
    }


def test_deep_merge_overwrites_non_dict_values():
    base = {
        "simulation": {
            "steps": 100,
        },
        "environment": "indoor",
    }
    override = {
        "simulation": "fast_mode",
        "environment": "outdoor",
    }

    result = deep_merge(base, override)

    assert result == {
        "simulation": "fast_mode",
        "environment": "outdoor",
    }


def test_deep_merge_does_not_modify_base_dict():
    base = {
        "simulation": {
            "steps": 100,
            "seed": 42,
        }
    }
    override = {
        "simulation": {
            "steps": 200,
        }
    }

    result = deep_merge(base, override)

    assert result == {
        "simulation": {
            "steps": 200,
            "seed": 42,
        }
    }
    assert base == {
        "simulation": {
            "steps": 100,
            "seed": 42,
        }
    }