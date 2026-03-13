"""utils/logger.py – structured logging using loguru."""

import sys
from pathlib import Path
from loguru import logger as _logger

from config import settings


def setup_logger() -> None:
    """Configure loguru sinks: stderr + rotating file."""
    _logger.remove()

    # Console sink
    _logger.add(
        sys.stderr,
        level=settings.LOG_LEVEL,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> – <level>{message}</level>"
        ),
        colorize=True,
    )

    # File sink (rotating, kept for 30 days)
    log_path = Path(settings.LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _logger.add(
        str(log_path),
        level=settings.LOG_LEVEL,
        rotation="50 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} – {message}",
        enqueue=True,
    )


setup_logger()
logger = _logger
