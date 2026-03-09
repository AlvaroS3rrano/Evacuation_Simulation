import logging
from pathlib import Path

def setup_run_logging(run_dir: Path, verbose: bool) -> None:
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "run.log"

    level = logging.DEBUG if verbose else logging.INFO
    logging.getLogger("matplotlib").setLevel(logging.WARNING)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")],
        force=True,
    )