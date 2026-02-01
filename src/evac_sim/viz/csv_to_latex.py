import pandas as pd
import re

def extract_case_info(case_name: str):
    """
    Returns (base_name, case_number or None)
    Example:
      'cruise_ship_case_1' -> ('cruise_ship', 1)
      'cruise_ship_representative' -> ('cruise_ship_representative', None)
    """
    s = str(case_name)
    m = re.search(r"(.*?)[_\s-]*case[_\s-]*(\d+)", s, flags=re.IGNORECASE)
    if m:
        base = m.group(1).rstrip("_- ")
        return base, int(m.group(2))
    return s, None

def format_case_name(case_name: str) -> str:
    """
    If case number exists -> 'Case N'
    Otherwise -> original name
    """
    base, num = extract_case_info(case_name)
    if num is not None:
        return f"Case {num}"
    return str(case_name)

def extract_case_number(case_name: str):
    m = re.search(r"case[_\s-]*(\d+)", case_name, re.IGNORECASE)
    return (0, int(m.group(1))) if m else (1, float("inf"))

def csv_to_latex_rows_casewise_config(
    csv_path: str,
    float_fmt="{:.4f}",
    time_fmt="{:.2f}",
    order_configurations=True,
    addlinespace_between_cases=False
) -> str:
    df = pd.read_csv(csv_path)

    needed = [
        "case_name","algorithm","awareness",
        "mean_remaining_path_risk","remaining_path_risk_var",
        "avg_path_length","min_time","max_time","avg_time","median_time","p90_time",
    ]
    df = df[needed].copy()

    df["Configuration"] = (
        df["algorithm"].astype(str) + ", " + df["awareness"].astype(str) + " Awareness"
    )

    agg = {
        "mean_remaining_path_risk": "mean",
        "remaining_path_risk_var": "mean",
        "avg_path_length": "mean",
        "min_time": "min",
        "max_time": "max",
        "avg_time": "mean",
        "median_time": "mean",
        "p90_time": "mean",
    }

    out = df.groupby(["case_name", "Configuration"], as_index=False).agg(agg)

    if order_configurations:
        cfg_order = [
            "Centrality, High Awareness",
            "Centrality, Low Awareness",
            "Efficient, High Awareness",
            "Efficient, Low Awareness",
        ]
        out["Configuration"] = pd.Categorical(out["Configuration"], categories=cfg_order, ordered=True)

    # order cases numerically; non-numbered last
    # Order cases by base name, then by case number (if any)
    case_info = out["case_name"].apply(extract_case_info)
    out["case_base"] = case_info.apply(lambda x: x[0])
    out["case_num"] = case_info.apply(lambda x: x[1] if x[1] is not None else 1e9)

    out = out.sort_values(
        ["case_base", "case_num", "Configuration"],
        kind="mergesort"  # stable sort
    ).drop(columns=["case_base", "case_num"])

    rows = []
    last_case = None
    for _, r in out.iterrows():
        case_label = format_case_name(r["case_name"])
        if addlinespace_between_cases and last_case is not None and case_label != last_case:
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
        last_case = case_label

    return "\n".join(rows)

def csv_to_latex_rows_for_case_config_means(
    csv_path: str,
    case_name: str,
    float_fmt="{:.4f}",
    time_fmt="{:.2f}",
    order_configurations=True
) -> str:
    """
    Build LaTeX rows for a single case_name, aggregated by (algorithm, awareness).

    Output columns (LaTeX row order):
        Configuration & Max Evac. Time (s) & Avg Evac. Time (s) & Avg Path Length & Mean RPR & RPR Var. \\

    Notes:
        - Max Evac. Time is computed as the mean of 'max_time' across groups/records for the same config.
        - Avg Evac. Time is computed as the mean of 'avg_time'.
        - Avg Path Length is computed as the mean of 'avg_path_length'.
        - Mean RPR is computed as the mean of 'mean_remaining_path_risk'.
        - RPR Var. is computed as the mean of 'remaining_path_risk_var'.
    """
    df = pd.read_csv(csv_path)

    needed = [
        "case_name", "algorithm", "awareness",
        "max_time", "avg_time", "avg_path_length",
        "mean_remaining_path_risk", "remaining_path_risk_var",
    ]
    df = df[needed].copy()

    # Filter to the requested case
    df_case = df[df["case_name"].astype(str) == str(case_name)].copy()
    if df_case.empty:
        raise ValueError(f"No rows found for case_name='{case_name}' in '{csv_path}'.")

    df_case["Configuration"] = (
        df_case["algorithm"].astype(str) + ", " + df_case["awareness"].astype(str) + " Awareness"
    )

    agg = {
        "max_time": "mean",
        "avg_time": "mean",
        "avg_path_length": "mean",
        "mean_remaining_path_risk": "mean",
        "remaining_path_risk_var": "mean",
    }

    out = df_case.groupby(["Configuration"], as_index=False).agg(agg)

    if order_configurations:
        cfg_order = [
            "Centrality, High Awareness",
            "Centrality, Low Awareness",
            "Efficient, High Awareness",
            "Efficient, Low Awareness",
        ]
        out["Configuration"] = pd.Categorical(
            out["Configuration"], categories=cfg_order, ordered=True
        )
        out = out.sort_values(["Configuration"])

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

def csv_to_latex_rows_scenario_compact_config(
    csv_path: str,
    stat: str = "mean",  # "mean" or "std"
    float_fmt="{:.4f}",
    time_fmt="{:.2f}",
    order_configurations=True
) -> str:
    """
    Build LaTeX rows for ONE SCENARIO (one CSV), aggregated across ALL case_name and runs,
    grouped by (algorithm, awareness).

    Output columns (LaTeX row order):
        Configuration & Max Evac. Time (s) & Avg Evac. Time (s) & Avg Path Length & Mean RPR & RPR Var. \\

    Notes:
        - Each cell is reported as mean ± std computed over ALL records in the CSV
          for the corresponding configuration (i.e., across all cases and runs).
        - This produces a compact 4-row table per scenario (Theme Park / Cruise Ship / Corridor).
    """
    if stat not in ("mean", "std"):
        raise ValueError("stat must be either 'mean' or 'std'.")

    df = pd.read_csv(csv_path)

    needed = [
        "algorithm", "awareness",
        "max_time", "avg_time", "avg_path_length",
        "mean_remaining_path_risk", "remaining_path_risk_var",
    ]
    df = df[needed].copy()

    df["Configuration"] = (
            df["algorithm"].astype(str) + ", " + df["awareness"].astype(str) + " Awareness"
    )

    # compute both mean and std once, then pick the desired 'stat'
    agg = {
        "max_time": ["mean", "std"],
        "avg_time": ["mean", "std"],
        "avg_path_length": ["mean", "std"],
        "mean_remaining_path_risk": ["mean", "std"],
        "remaining_path_risk_var": ["mean", "std"],
    }
    out = df.groupby(["Configuration"], as_index=False).agg(agg)

    # flatten columns: max_time_mean, max_time_std, ...
    out.columns = [
        "_".join([x for x in col if x]).rstrip("_") if isinstance(col, tuple) else col
        for col in out.columns
    ]

    if order_configurations:
        cfg_order = [
            "Centrality, High Awareness",
            "Centrality, Low Awareness",
            "Efficient, High Awareness",
            "Efficient, Low Awareness",
        ]
        out["Configuration"] = pd.Categorical(
            out["Configuration"], categories=cfg_order, ordered=True
        )
        out = out.sort_values(["Configuration"])

    rows = []
    for _, r in out.iterrows():
        rows.append(
            f"{r['Configuration']} & "
            f"{time_fmt.format(r[f'max_time_{stat}'])} & "
            f"{time_fmt.format(r[f'avg_time_{stat}'])} & "
            f"{time_fmt.format(r[f'avg_path_length_{stat}'])} & "
            f"{float_fmt.format(r[f'mean_remaining_path_risk_{stat}'])} & "
            f"{float_fmt.format(r[f'remaining_path_risk_var_{stat}'])} \\\\"
        )

    return "\n".join(rows)


# path = "../../../results/CSV/Cruise_Ship_experiment_metrics.csv"
path = "../../../results/CSV/Theme Park_experiment_metrics.csv"
# path = "../../../results/CSV/corridor_experiment_metrics.csv"
latex_rows = csv_to_latex_rows_casewise_config(path)
# latex_rows = csv_to_latex_rows_for_case_config_means(path, "example_case")
# latex_rows = csv_to_latex_rows_scenario_compact_config(path, stat="std")
print(latex_rows)


