"""
Centralized logging utility for the data pipeline.
Provides consistent logging configuration across all modules.
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


def get_logger(
    name: str,
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically module name)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path. If None, logs to logs/{name}.log
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger("sec_fetcher")
        >>> logger.info("Fetching SEC filings...")
    """
    # Create logger
    logger = logging.getLogger(name)

    # Set log level from environment or default to INFO
    if log_level is None:
        import os
        log_level = os.getenv("LOG_LEVEL", "INFO")

    logger.setLevel(getattr(logging, log_level.upper()))

    # Avoid duplicate handlers if logger already configured
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation
    if log_file is None:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"{name}.log"

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def set_log_level(logger: logging.Logger, level: str):
    """
    Change log level for an existing logger.

    Args:
        logger: Logger instance
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger.setLevel(getattr(logging, level.upper()))
    for handler in logger.handlers:
        handler.setLevel(getattr(logging, level.upper()))


# Create a default logger for the utils module
logger = get_logger("utils")
