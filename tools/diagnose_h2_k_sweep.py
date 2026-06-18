from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

# Command example:
# python tools\diagnose_h2_k_sweep.py --k-values 3 6 8 10 12 15 --config congestion_heuristics.yaml --case congestion_two_exits --out-root .\runs\diagnostics_h2_k_sweep -v
#

def run_h2_for_k(
    *,
    k: int,
    config: str,
    case: str,
    out_root: Path,
    verbose: bool,
) -> dict[str, Any]:
    k_out_root = out_root / f"h2_k{k}"

    command = [
        sys.executable,
        "tools/diagnose_congestion_heuristics.py",
        "--config",
        config,
        "--case",
        case,
        "--heuristics",
        "h2",
        "--out-root",
        str(k_out_root),
        "--extra-arg=--horizon-k",
        "--extra-arg",
        str(k),
    ]

    if verbose:
        command.append("-v")

    print("\n" + "=" * 80)
    print(f"Running h2 with k={k}")
    print(" ".join(command))
    print("=" * 80)

    completed = subprocess.run(
        command,
        text=True,
        check=False,
    )

    report_path = k_out_root / "diagnostics_report.json"

    if not report_path.exists():
        return {
            "k": k,
            "status": "ERROR",
            "return_code": completed.returncode,
            "reason": "diagnostics_report.json was not generated",
        }

    diagnostics = json.loads(report_path.read_text(encoding="utf-8"))

    if not diagnostics:
        return {
            "k": k,
            "status": "ERROR",
            "return_code": completed.returncode,
            "reason": "Empty diagnostics report",
        }

    diag = diagnostics[0]
    counts = diag.get("counts", {})

    return {
        "k": k,
        "status": diag.get("status"),
        "return_code": diag.get("return_code"),
        "duration_seconds": diag.get("duration_seconds"),
        "stopped": counts.get("group_stopped", 0),
        "resumed": counts.get("group_resumed", 0),
        "ready": counts.get("capacity_ready", 0),
        "blocked": counts.get("capacity_blocked", 0)
        + counts.get("path_capacity_blocked", 0),
        "pending": counts.get("capacity_pending", 0),
        "future_skipped": counts.get("capacity_future_reservation_skipped", 0)
        + counts.get("path_capacity_future_reservation_skipped", 0),
        "backtracks": counts.get("reroute_backtrack", 0),
        "max_frames_stop": counts.get("max_frames_stop", 0),
        "error_or_traceback": counts.get("error_or_traceback", 0),
        "stuck_groups": len(diag.get("possible_stuck_groups", [])),
        "top_blocked_resources": diag.get("top_blocked_resources", {}),
        "reasons": "; ".join(diag.get("reasons", [])),
        "out_dir": diag.get("out_dir"),
        "log_file": diag.get("log_file"),
    }


def write_summary_files(
    *,
    rows: list[dict[str, Any]],
    out_root: Path,
) -> None:
    out_root.mkdir(parents=True, exist_ok=True)

    json_path = out_root / "h2_k_sweep_summary.json"
    csv_path = out_root / "h2_k_sweep_summary.csv"
    md_path = out_root / "h2_k_sweep_summary.md"

    json_path.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    fieldnames = [
        "k",
        "status",
        "return_code",
        "duration_seconds",
        "stopped",
        "resumed",
        "ready",
        "blocked",
        "pending",
        "future_skipped",
        "backtracks",
        "max_frames_stop",
        "error_or_traceback",
        "stuck_groups",
        "reasons",
        "log_file",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    lines: list[str] = []
    lines.append("# H2 horizon-k sweep")
    lines.append("")
    lines.append(
        "| k | Status | Duration | Stopped | Resumed | Ready | Blocked | Pending | Future skipped | Backtracks | Stuck groups | Main reason |"
    )
    lines.append(
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    )

    for row in rows:
        duration = row.get("duration_seconds")
        duration_text = f"{duration:.2f}" if isinstance(duration, (int, float)) else "-"

        reason = str(row.get("reasons", "")).replace("|", "\\|")

        lines.append(
            "| {k} | {status} | {duration} | {stopped} | {resumed} | {ready} | "
            "{blocked} | {pending} | {future_skipped} | {backtracks} | "
            "{stuck_groups} | {reason} |".format(
                k=row.get("k"),
                status=row.get("status"),
                duration=duration_text,
                stopped=row.get("stopped", 0),
                resumed=row.get("resumed", 0),
                ready=row.get("ready", 0),
                blocked=row.get("blocked", 0),
                pending=row.get("pending", 0),
                future_skipped=row.get("future_skipped", 0),
                backtracks=row.get("backtracks", 0),
                stuck_groups=row.get("stuck_groups", 0),
                reason=reason,
            )
        )

    lines.append("")
    lines.append("## Top blocked resources by k")
    lines.append("")

    for row in rows:
        lines.append(f"### k={row.get('k')}")
        top_resources = row.get("top_blocked_resources", {})

        if not top_resources:
            lines.append("- No blocked resources.")
        else:
            for resource, count in top_resources.items():
                lines.append(f"- `{resource}`: {count}")

        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    print("\nSummary generated:")
    print(f"- {json_path}")
    print(f"- {csv_path}")
    print(f"- {md_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run h2 diagnostics with different horizon-k values."
    )
    parser.add_argument(
        "--config",
        default="congestion_heuristics.yaml",
    )
    parser.add_argument(
        "--case",
        default="congestion_two_exits",
    )
    parser.add_argument(
        "--k-values",
        nargs="+",
        type=int,
        default=[3, 6, 8, 10, 12],
    )
    parser.add_argument(
        "--out-root",
        default="./runs/diagnostics_h2_k_sweep",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_root = Path(args.out_root)

    rows: list[dict[str, Any]] = []

    for k in args.k_values:
        row = run_h2_for_k(
            k=k,
            config=args.config,
            case=args.case,
            out_root=out_root,
            verbose=args.verbose,
        )
        rows.append(row)

    write_summary_files(
        rows=rows,
        out_root=out_root,
    )

    print("\nQuick comparison:")
    for row in rows:
        print(
            "k={k} | {status} | stopped={stopped} | resumed={resumed} | "
            "blocked={blocked} | pending={pending} | stuck={stuck_groups}".format(
                k=row.get("k"),
                status=row.get("status"),
                stopped=row.get("stopped", 0),
                resumed=row.get("resumed", 0),
                blocked=row.get("blocked", 0),
                pending=row.get("pending", 0),
                stuck_groups=row.get("stuck_groups", 0),
            )
        )


if __name__ == "__main__":
    main()