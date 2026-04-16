import pandas as pd
import sqlite3

from evac_sim.db.repositories.experiments import (
    get_all_experiments,
    get_all_experiment_metrics,
)


def export_experiments_to_csv(
    db_path: str,
    csv_path: str = "experiments.csv",
) -> str:
    conn = sqlite3.connect(db_path)
    try:
        df = get_all_experiments(conn)
        df.to_csv(csv_path, index=False)
        return csv_path
    finally:
        conn.close()


def export_experiment_metrics_to_csv(
    db_path: str,
    csv_path: str = "experiment_metrics.csv",
    include_experiment_context: bool = True,
) -> str:
    conn = sqlite3.connect(db_path)
    try:
        df = get_all_experiment_metrics(conn, include_experiment_context)
        df.to_csv(csv_path, index=False)
        return csv_path
    finally:
        conn.close()