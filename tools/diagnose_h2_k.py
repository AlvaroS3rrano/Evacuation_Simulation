from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run h2 with different k values and compare the results."
    )

    parser.add_argument(
        "--config",
        required=True,
        help="YAML config filename inside configs/ or explicit path.",
    )

    parser.add_argument(
        "--k-values",
        nargs="+",
        type=int,
        required=True,
        help="k values to diagnose. Example: --k-values 2 3 4 5 6 8 10",
    )

    parser.add_argument(
        "--cases",
        nargs="*",
        default=None,
        help="Optional case ids. By default all cases are executed.",
    )

    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs/h2_k_diagnostic"),
        help="Output root for the diagnostic runs.",
    )

    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue if a k/case combination fails.",
    )

    return parser.parse_args()


def run_for_k(args: argparse.Namespace, k_value: int) -> Path:
    run_all_script = PROJECT_ROOT / "tools" / "run_all_congestion_heuristics.py"
    k_dir = (PROJECT_ROOT / args.runs_dir / f"k_{k_value:02d}").resolve()

    command = [
        sys.executable,
        str(run_all_script),
        "--config",
        args.config,
        "--heuristics",
        "h2",
        "--horizon-k",
        str(k_value),
        "--runs-dir",
        str(k_dir),
        "--skip-scenario-report",
        "--skip-comparison",
    ]

    if args.cases:
        command.extend(["--cases", *args.cases])

    if args.continue_on_error:
        command.append("--continue-on-error")

    print()
    print("=" * 80)
    print(f"Running h2 diagnostic for k={k_value}")
    print("=" * 80)
    print(" ".join(str(part) for part in command))

    subprocess.run(
        command,
        cwd=str(PROJECT_ROOT),
        check=True,
    )

    return k_dir


def read_metric_file(csv_path: Path) -> dict[str, float]:
    df = pd.read_csv(csv_path)

    values: dict[str, float] = {}

    for metric in [
        "avg_evac_time",
        "p90_evac_time",
        "max_evac_time",
        "avg_density_exposure",
        "high_density_agent_ratio",
    ]:
        for column in [f"{metric}_weighted", metric]:
            if column in df.columns:
                values[metric] = float(pd.to_numeric(df[column], errors="coerce").mean())
                break

    return values


def collect_summary(k_dirs: dict[int, Path]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []

    for k_value, k_dir in k_dirs.items():
        for csv_path in sorted(
            k_dir.glob("h2/*/artifacts/csv/comparison_metrics.csv")
        ):
            case_id = csv_path.parents[2].name
            values = read_metric_file(csv_path)

            rows.append(
                {
                    "k": k_value,
                    "case_id": case_id,
                    **values,
                    "metrics_path": str(csv_path),
                }
            )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def write_report(summary: pd.DataFrame, output_path: Path) -> None:
    lines: list[str] = []

    lines.append("# h2 k diagnostic")
    lines.append("")
    lines.append("Lower values are better for all listed metrics.")
    lines.append("")

    if summary.empty:
        lines.append("_No metric files were found._")
    else:
        aggregate = (
            summary
            .groupby("k", as_index=False)
            .agg(
                n_cases=("case_id", "nunique"),
                avg_evac_time_mean=("avg_evac_time", "mean"),
                p90_evac_time_mean=("p90_evac_time", "mean"),
                max_evac_time_mean=("max_evac_time", "mean"),
                avg_density_exposure_mean=("avg_density_exposure", "mean"),
                high_density_agent_ratio_mean=("high_density_agent_ratio", "mean"),
            )
            .sort_values("avg_evac_time_mean")
        )

        lines.append("## Aggregate by k")
        lines.append("")
        lines.append(aggregate.to_markdown(index=False))
        lines.append("")

        lines.append("## Case-level values")
        lines.append("")
        lines.append(summary.sort_values(["case_id", "k"]).to_markdown(index=False))

    output_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()

    k_dirs: dict[int, Path] = {}

    for k_value in args.k_values:
        k_dirs[k_value] = run_for_k(args, k_value)

    output_dir = (PROJECT_ROOT / args.runs_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    summary = collect_summary(k_dirs)

    summary_path = output_dir / "h2_k_diagnostic_summary.csv"
    report_path = output_dir / "h2_k_diagnostic_report.md"

    summary.to_csv(summary_path, index=False)
    write_report(summary, report_path)

    print()
    print("=" * 80)
    print("h2 k diagnostic generated")
    print("=" * 80)
    print(f"Summary: {summary_path}")
    print(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
