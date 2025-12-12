# src/utils/logging_config.py
"""Logging configuration for the pipeline"""

import logging
import sys
import io
import os
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler


def setup_logging(
    log_dir: str = None,
    log_level: str = 'INFO',
    log_to_file: bool = True,
    log_to_console: bool = True
):
    """
    Setup logging configuration
    
    Args:
        log_dir: Directory for log files (defaults to Data_Pipeline/logs)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Whether to log to file
        log_to_console: Whether to log to console
    """
    # Skip custom logging setup when running inside Airflow
    # Airflow manages its own logging and custom setup causes recursion errors
    if 'AIRFLOW_HOME' in os.environ or 'AIRFLOW__CORE__DAGS_FOLDER' in os.environ:
        return
    
    # FIX: Set console to UTF-8 for Windows Unicode support
    if sys.platform == 'win32':
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            elif hasattr(sys.stdout, 'buffer'):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        except Exception:
            # sys.stdout might be replaced (e.g. by Airflow) and not support these operations
            pass
    
    # Create log directory
    if log_dir is None:
        current_file = Path(__file__)
        log_dir = current_file.parent.parent.parent / 'logs'
    
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    logger.handlers = []
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
    
    # File handler (with rotation)
    if log_to_file:
        log_file = log_dir / f"pipeline_{datetime.now().strftime('%Y%m%d')}.log"
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'  # FIX: Use UTF-8 encoding for Unicode support
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    
    # Also create error-only log
    if log_to_file:
        error_log_file = log_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding='utf-8'  # FIX: Use UTF-8 encoding for Unicode support
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)
    
    logger.info(f"Logging initialized: {log_level} level, log_dir: {log_dir}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Initialize logging on import
setup_logging()


if __name__ == '__main__':
    # Test logging
    logger = get_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")