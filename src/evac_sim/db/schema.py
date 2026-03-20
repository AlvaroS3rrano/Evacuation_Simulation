import sqlite3

def create_risk_table(connection: sqlite3.Connection, force_reset: bool = False):
    try:
        with connection:
            if force_reset:
                connection.execute("DROP TABLE IF EXISTS risk")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_data
                (
                    frame INTEGER NOT NULL,
                    area TEXT NOT NULL,
                    risk_level REAL NOT NULL,
                    PRIMARY KEY( frame, area )
                    )
                """
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating risk_data table: {e}")

def create_group_decisions_table(
    connection: sqlite3.Connection,
    force_reset: bool = False,
) -> None:
    try:
        with connection:
            if force_reset:
                connection.execute("DROP TABLE IF EXISTS group_path_data")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS group_path_data (
                    frame INTEGER NOT NULL,
                    group_id INTEGER NOT NULL,
                    algorithm TEXT NOT NULL,
                    awareness TEXT NOT NULL,
                    current_area TEXT NOT NULL,
                    next_path TEXT NOT NULL,
                    est_risk_mean REAL NOT NULL,
                    est_risk_max REAL NOT NULL,
                    est_risk_min REAL NOT NULL,
                    est_risk_var REAL NOT NULL,
                    risk_now REAL NOT NULL,
                    PRIMARY KEY (frame, group_id, algorithm, awareness)
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_group_path_frame
                ON group_path_data(frame)
                """
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating group_path_data table: {e}")

def create_paths_table(connection, force_reset=False):
    with connection:
        if force_reset:
            connection.execute("DROP TABLE IF EXISTS paths")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                cost REAL NOT NULL,
                path TEXT NOT NULL,
                betweenness REAL,
                UNIQUE(source, target)
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_paths_source_target
            ON paths(source, target)
            """
        )

def create_agent_area_table(connection, force_reset=False):
    with connection:
        if force_reset:
            connection.execute("DROP TABLE IF EXISTS agent_area_data")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_area_data (
                frame INTEGER NOT NULL,
                agent_id INTEGER NOT NULL,
                area TEXT NOT NULL,
                risk_level REAL NOT NULL,
                PRIMARY KEY (frame, agent_id)
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_area_frame
            ON agent_area_data(frame)
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_area_agent
            ON agent_area_data(agent_id)
            """
        )

def create_experiments_tables(
    connection: sqlite3.Connection,
    force_reset: bool = False,
) -> None:
    try:
        with connection:
            if force_reset:
                connection.execute("DROP TABLE IF EXISTS experiment_metrics")
                connection.execute("DROP TABLE IF EXISTS experiments")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_name TEXT NOT NULL UNIQUE,
                    risk_nodes TEXT NOT NULL,
                    source_nodes TEXT NOT NULL,
                    agents_per_source TEXT NOT NULL,
                    random_seed INTEGER NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS experiment_metrics (
                    experiment_id INTEGER NOT NULL,
                    agent_group_id TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    awareness REAL NOT NULL,
                    n_records INTEGER NOT NULL,
                    mean_remaining_path_risk REAL NOT NULL,
                    remaining_path_risk_var REAL NOT NULL,
                    cumulative_risk_exposure REAL NOT NULL,
                    avg_path_cost REAL NOT NULL,
                    min_time REAL NOT NULL,
                    avg_time REAL NOT NULL,
                    median_time REAL NOT NULL,
                    p90_time REAL NOT NULL,
                    max_time REAL NOT NULL,
                    PRIMARY KEY (experiment_id, agent_group_id, algorithm, awareness),
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_experiment_metrics_experiment_id
                ON experiment_metrics(experiment_id)
                """
            )
    except sqlite3.Error as e:
        raise RuntimeError(f"Error creating experiment tables: {e}")
