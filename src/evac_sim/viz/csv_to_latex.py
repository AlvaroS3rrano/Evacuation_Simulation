import re
import pandas as pd

# ----------------------------
# Constants / shared utilities
# ----------------------------

CFG_ORDER = [
    "Centrality, High Awareness",
    "Centrality, Low Awareness",
    "Efficient, High Awareness",
    "Efficient, Low Awareness",
]

# Metric spec: (column_name, is_time_metric)
SCENARIO_METRICS = [
    ("max_time", True),
    ("avg_time", True),
    ("avg_path_length", True),
    ("mean_remaining_path_risk", False),
    ("remaining_path_risk_var", False),
]


def _make_configuration(df: pd.DataFrame) -> pd.Series:
    """Builds the 'Configuration' label from algorithm + awareness."""
    return (
        df["algorithm"].astype(str)
        + ", "
        + df["awareness"].astype(str)
        + " Awareness"
    )


def _order_configurations(df: pd.DataFrame, col: str = "Configuration") -> pd.DataFrame:
    """Applies a categorical ordering to configuration rows."""
    df[col] = pd.Categorical(df[col], categories=CFG_ORDER, ordered=True)
    return df.sort_values([col], kind="mergesort")


def _flatten_agg_columns(columns) -> list[str]:
    """Flattens MultiIndex columns from pandas aggregation into 'col_stat' names."""
    flat = []
    for c in columns:
        if isinstance(c, tuple):
            flat.append("_".join([x for x in c if x]).rstrip("_"))
        else:
            flat.append(c)
    return flat


# ----------------------------
# Case name helpers
# ----------------------------

def extract_case_info(case_name: str) -> tuple[str, int | None]:
    """
    Returns (base_name, case_number or None).

    Examples:
      'cruise_ship_case_1' -> ('cruise_ship', 1)
      'cruise_ship_representative' -> ('cruise_ship_representative', None)
    """
    s = str(case_name)
    m = re.search(r"(.*?)[_\s-]*case[_\s-]*(\d+)", s, flags=re.IGNORECASE)
    if not m:
        return s, None

    base = m.group(1).rstrip("_- ")
    return base, int(m.group(2))


def format_case_name(case_name: str) -> str:
    """If a case number exists -> 'Case N', otherwise returns the original name."""
    _, num = extract_case_info(case_name)
    return f"Case {num}" if num is not None else str(case_name)


# ----------------------------
# Aggregation helpers
# ----------------------------

def _read_csv_columns(csv_path: str, columns: list[str]) -> pd.DataFrame:
    """Reads only the required columns from a CSV (keeps code DRY)."""
    return pd.read_csv(csv_path, usecols=columns).copy()


def _aggregate_by_configuration(
    df: pd.DataFrame,
    metrics: dict[str, str | list[str]],
    group_cols: list[str],
    order_configurations: bool = True
) -> pd.DataFrame:
    """
    Aggregates df over group_cols using metrics dict and returns aggregated dataframe.
    Optionally applies configuration ordering if 'Configuration' is present.
    """
    out = df.groupby(group_cols, as_index=False).agg(metrics)

    # Flatten MultiIndex columns if needed
    out.columns = _flatten_agg_columns(out.columns)

    if order_configurations and "Configuration" in out.columns:
        out = _order_configurations(out, "Configuration")

    return out


# ----------------------------
# 1) Casewise table (case_name x configuration)
# ----------------------------

def csv_to_latex_rows_casewise_config(
    csv_path: str,
    float_fmt: str = "{:.4f}",
    time_fmt: str = "{:.2f}",
    order_configurations: bool = True,
    addlinespace_between_cases: bool = False
) -> str:
    columns = [
        "case_name", "algorithm", "awareness",
        "mean_remaining_path_risk", "remaining_path_risk_var",
        "avg_path_length", "min_time", "max_time", "avg_time", "median_time", "p90_time",
    ]
    df = _read_csv_columns(csv_path, columns)
    df["Configuration"] = _make_configuration(df)

    metrics = {
        "mean_remaining_path_risk": "mean",
        "remaining_path_risk_var": "mean",
        "avg_path_length": "mean",
        "min_time": "min",
        "max_time": "max",
        "avg_time": "mean",
        "median_time": "mean",
        "p90_time": "mean",
    }

    out = _aggregate_by_configuration(
        df=df,
        metrics=metrics,
        group_cols=["case_name", "Configuration"],
        order_configurations=order_configurations,
    )

    # Order cases by (base_name, case_number), keeping stable order within ties
    case_info = out["case_name"].map(extract_case_info)
    out["case_base"] = case_info.map(lambda x: x[0])
    out["case_num"] = case_info.map(lambda x: x[1] if x[1] is not None else 1_000_000_000)

    out = out.sort_values(
        ["case_base", "case_num", "Configuration"],
        kind="mergesort",
    ).drop(columns=["case_base", "case_num"])

    rows = []
    last_case_label = None

    for _, r in out.iterrows():
        case_label = format_case_name(r["case_name"])

        if addlinespace_between_cases and last_case_label is not None and case_label != last_case_label:
            rows.append(r"\addlinespace")

        rows.append(
            f"{case_label} & {r['Configuration']} & "
            f"{float_fmt.format(r['mean_remaining_path_risk'])} & "
            f"{float_fmt.format(r['remaining_path_risk_var'])} & "
            f"{time_fmt.format(r['avg_path_length'])} & "
            f"{time_fmt.format(r['min_time'])} & "
            f"{time_fmt.format(r['max_time'])} & "
            f"{time_fmt.format(r['avg_time'])} & "
            f"{time_fmt.format(r['median_time'])} & "
            f"{time_fmt.format(r['p90_time'])} \\\\"
        )

        last_case_label = case_label

    return "\n".join(rows)


# ----------------------------
# 2) Single case table (configuration only) - MEANS
# ----------------------------

def csv_to_latex_rows_for_case_config_means(
    csv_path: str,
    case_name: str,
    float_fmt: str = "{:.4f}",
    time_fmt: str = "{:.2f}",
    order_configurations: bool = True
) -> str:
    """
    Builds LaTeX rows for a single case, aggregated by (algorithm, awareness).

    Output columns:
      Configuration & Max Evac. Time & Avg Evac. Time & Avg Path Length & Mean RPR & RPR Var \\\\
    """
    columns = [
        "case_name", "algorithm", "awareness",
        "max_time", "avg_time", "avg_path_length",
        "mean_remaining_path_risk", "remaining_path_risk_var",
    ]
    df = _read_csv_columns(csv_path, columns)

    df = df[df["case_name"].astype(str) == str(case_name)].copy()
    if df.empty:
        raise ValueError(f"No rows found for case_name='{case_name}' in '{csv_path}'.")

    df["Configuration"] = _make_configuration(df)

    metrics = {
        "max_time": "mean",
        "avg_time": "mean",
        "avg_path_length": "mean",
        "mean_remaining_path_risk": "mean",
        "remaining_path_risk_var": "mean",
    }

    out = _aggregate_by_configuration(
        df=df,
        metrics=metrics,
        group_cols=["Configuration"],
        order_configurations=order_configurations,
    )

    rows = []
    for _, r in out.iterrows():
        rows.append(
            f"{r['Configuration']} & "
            f"{time_fmt.format(r['max_time'])} & "
            f"{time_fmt.format(r['avg_time'])} & "
            f"{time_fmt.format(r['avg_path_length'])} & "
            f"{float_fmt.format(r['mean_remaining_path_risk'])} & "
            f"{float_fmt.format(r['remaining_path_risk_var'])} \\\\"
        )

    return "\n".join(rows)


# ----------------------------
# 3) Scenario compact table (configuration only) - mean/std/mean±std
# ----------------------------

def _aggregate_scenario_compact_config(
    csv_path: str,
    order_configurations: bool = True,
) -> pd.DataFrame:
    """Reads a scenario CSV and aggregates mean/std per configuration."""
    columns = ["algorithm", "awareness"] + [m for m, _ in SCENARIO_METRICS]
    df = _read_csv_columns(csv_path, columns)
    df["Configuration"] = _make_configuration(df)

    metrics = {m: ["mean", "std"] for m, _ in SCENARIO_METRICS}

    out = _aggregate_by_configuration(
        df=df,
        metrics=metrics,
        group_cols=["Configuration"],
        order_configurations=order_configurations,
    )
    return out


def csv_to_latex_rows_scenario_compact_config(
    csv_path: str,
    mode: str = "mean",  # "mean", "std", "mean+std"
    float_fmt: str = "{:.4f}",
    time_fmt: str = "{:.2f}",
    order_configurations: bool = True,
    do_print: bool = False,
) -> str:
    """
    Returns (and optionally prints) LaTeX rows for a scenario aggregated by configuration.

    Modes:
      - "mean":     prints only means
      - "std":      prints only standard deviations
      - "mean+std": prints '$mean \\pm std$' per cell
    """
    mode = str(mode).strip().lower()
    mean_pm_aliases = {"mean+std", "mean±std", "mean_pm_std", "meanpmstd"}
    valid = {"mean", "std"} | mean_pm_aliases
    if mode not in valid:
        raise ValueError("mode must be one of: 'mean', 'std', 'mean+std'.")

    agg = _aggregate_scenario_compact_config(csv_path, order_configurations)

    def fmt(val, is_time: bool) -> str:
        return (time_fmt if is_time else float_fmt).format(val)

    def cell(r, metric: str, is_time: bool) -> str:
        if mode in ("mean", "std"):
            return fmt(r[f"{metric}_{mode}"], is_time)
        # mean ± std
        return f"${fmt(r[f'{metric}_mean'], is_time)} \\pm {fmt(r[f'{metric}_std'], is_time)}$"

    rows = []
    for _, r in agg.iterrows():
        parts = [str(r["Configuration"])]
        parts += [cell(r, metric, is_time) for metric, is_time in SCENARIO_METRICS]
        rows.append(" & ".join(parts) + r" \\")

    result = "\n".join(rows)
    if do_print:
        print(result)
    return result

if __name__ == "__main__":
    CSV_PATHS = {
        "cruise": "../../../results/CSV/Cruise_Ship_experiment_metrics.csv",
        "theme_park": "../../../results/CSV/Theme Park_experiment_metrics.csv",
        "corridor": "../../../results/CSV/corridor_experiment_metrics.csv",
    }

    scenario = "corridor"  # change to "theme_park" or "corridor"
    case = "example_case"
    mode = "mean+std"    # "mean", "std", "mean+std"4

    # latex_rows = csv_to_latex_rows_casewise_config(CSV_PATHS[scenario])
    # latex_rows = csv_to_latex_rows_for_case_config_means(CSV_PATHS[scenario], "example_case")
    latex_rows = csv_to_latex_rows_scenario_compact_config(CSV_PATHS[scenario], mode=mode)
    print(latex_rows)


