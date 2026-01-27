import pandas as pd
import re

def format_case_name(case_name: str) -> str:
    m = re.search(r"case[_\s-]*(\d+)", case_name, re.IGNORECASE)
    return f"Case {m.group(1)}" if m else "Case"

def extract_case_number(case_name: str):
    m = re.search(r"case[_\s-]*(\d+)", case_name, re.IGNORECASE)
    return (0, int(m.group(1))) if m else (1, float("inf"))

def csv_to_latex_rows_casewise_config(
    csv_path: str,
    float_fmt="{:.6f}",
    time_fmt="{:.2f}",
    order_configurations=True,
    addlinespace_between_cases=False
) -> str:
    df = pd.read_csv(csv_path)

    needed = [
        "case_name","algorithm","awareness",
        "mean_remaining_path_risk","remaining_path_risk_var","cumulative_risk_exposure",
        "avg_path_length","min_time","max_time","avg_time","median_time","p90_time",
    ]
    df = df[needed].copy()

    df["Configuration"] = (
        df["algorithm"].astype(str) + ", " + df["awareness"].astype(str) + " Awareness"
    )

    agg = {
        "mean_remaining_path_risk": "mean",
        "remaining_path_risk_var": "mean",
        "cumulative_risk_exposure": "mean",
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
    out["case_sort"] = out["case_name"].apply(extract_case_number)
    out = out.sort_values(["case_sort", "Configuration"]).drop(columns=["case_sort"])

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
            f"{float_fmt.format(r['cumulative_risk_exposure'])} & "
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
    float_fmt="{:.6f}",
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



# path = "../../../results/CSV/Cruise_Ship_experiment_metrics.csv"
path = "../../../results/CSV/Theme Park_experiment_metrics.csv"
# path = "../../--/results/CSV/corridor_experiment_metrics.csv"
#latex_rows = csv_to_latex_rows_casewise_config(path)
latex_rows = csv_to_latex_rows_for_case_config_means(path, "representative_case_theme_park")
print(latex_rows)


