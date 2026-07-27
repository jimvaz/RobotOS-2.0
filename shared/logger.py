"""Shared logging configuration."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger


def configure_logging(
    *,
    level: str = "INFO",
    log_file: str | Path | None = None,
) -> None:
    """Configure console logging and an optional rotating file log."""

    logger.remove()
    logger.add(
        sys.stderr,
        level=level.upper(),
        enqueue=True,
        backtrace=False,
        diagnose=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan> | <level>{message}</level>"
        ),
    )

    if log_file is not None:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            path,
            level=level.upper(),
            enqueue=True,
            rotation="5 MB",
            retention=5,
            compression="zip",
        )
