from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_markdown_report(
    *,
    out_dir: Path,
    combined: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    best_by_metric: pd.DataFrame,
    metrics: list[str],
    main_metric: str,
    baseline: str,
    visual_pdf_paths: list[Path] | None = None,
) -> Path:
    report_path = out_dir / "comparison_report.md"
    main_column = f"{main_metric}_weighted"
    pct_column = f"{main_column}_pct_vs_{baseline}"

    lines: list[str] = []
    lines.append("# Congestion heuristic comparison")
    lines.append("")
    lines.append(f"Main metric: `{main_column}`")
    lines.append(f"Baseline: `{baseline}`")
    lines.append("")

    lines.append("## Summary by case")
    lines.append("")

    for case_id, case_df in summary.groupby("case_id"):
        lines.append(f"### {case_id}")
        lines.append("")

        compact_columns = ["heuristic", "groups", "total_n_records", "metrics_source"]
        for metric in metrics:
            column = f"{metric}_weighted"
            if column in case_df.columns:
                compact_columns.append(column)

        compact = case_df[[column for column in compact_columns if column in case_df.columns]].copy()
        lines.append(compact.to_markdown(index=False))
        lines.append("")

        case_comp = comparison[comparison["case_id"] == case_id]

        lines.append(f"Change vs `{baseline}` by metric:")
        lines.append("")

        for metric in metrics:
            metric_column = f"{metric}_weighted"
            pct_column = f"{metric_column}_pct_vs_{baseline}"

            if metric_column not in case_comp.columns or pct_column not in case_comp.columns:
                continue

            deltas = case_comp[["heuristic", metric_column, pct_column]].copy()

            lines.append(f"#### `{metric}`")
            lines.append("")
            lines.append(deltas.to_markdown(index=False))
            lines.append("")

    lines.append("## Best heuristic by metric")
    lines.append("")
    lines.append(best_by_metric.to_markdown(index=False) if not best_by_metric.empty else "_No best-metric data available._")
    lines.append("")

    if visual_pdf_paths:
        lines.append("## Visual comparison PDFs")
        lines.append("")
        for pdf_path in visual_pdf_paths:
            lines.append(f"- `{pdf_path.as_posix()}`")
        lines.append("")

    lines.append("## Input metric files")
    lines.append("")
    input_files = combined[["case_id", "heuristic", "metrics_source", "metrics_path"]].drop_duplicates()
    lines.append(input_files.to_markdown(index=False))
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def write_outputs(
    *,
    out_dir: Path,
    combined: pd.DataFrame,
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    best_by_metric: pd.DataFrame,
    metrics: list[str],
    main_metric: str,
    baseline: str,
    visual_pdf_paths: list[Path] | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out_dir / "combined_metrics.csv", index=False)
    summary.to_csv(out_dir / "summary_by_case_heuristic.csv", index=False)
    comparison.to_csv(out_dir / "comparison_vs_baseline.csv", index=False)
    best_by_metric.to_csv(out_dir / "best_by_metric.csv", index=False)

    report = write_markdown_report(
        out_dir=out_dir,
        combined=combined,
        summary=summary,
        comparison=comparison,
        best_by_metric=best_by_metric,
        metrics=metrics,
        main_metric=main_metric,
        baseline=baseline,
        visual_pdf_paths=visual_pdf_paths,
    )

    print(f"Report written to: {report}")
