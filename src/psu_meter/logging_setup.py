from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
LOG_FILE_NAME = "psu-meter.log"
LOG_FILE_MAX_BYTES = 1_000_000
LOG_FILE_BACKUPS = 5


def configure_logging(console_level: str, log_dir: str) -> None:
    """Console at ``console_level``; full DEBUG detail in a rotating file under ``log_dir``."""
    formatter = logging.Formatter(LOG_FORMAT)
    console = logging.StreamHandler()
    console.setLevel(console_level)
    console.setFormatter(formatter)

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = RotatingFileHandler(
        Path(log_dir) / LOG_FILE_NAME,
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUPS,
    )
    log_file.setLevel(logging.DEBUG)
    log_file.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(log_file)
