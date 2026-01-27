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

# path = "../../results/CSV/Cruise_Ship_experiment_metrics.csv"
# path = "../../results/CSV/Theme Park_experiment_metrics.csv"
path = "../../results/CSV/corridor_experiment_metrics.csv"
latex_rows = csv_to_latex_rows_casewise_config(path)
print(latex_rows)
