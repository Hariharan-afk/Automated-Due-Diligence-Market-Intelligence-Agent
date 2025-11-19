# src/utils/logging_config.py
"""Structured logging configuration for the pipeline"""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import json


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data)


class ContextFilter(logging.Filter):
    """Filter to add context information to log records"""
    
    def __init__(self, context: Optional[dict] = None):
        super().__init__()
        self.context = context or {}
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Add context to record"""
        if not hasattr(record, "extra_fields"):
            record.extra_fields = {}
        record.extra_fields.update(self.context)
        return True


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False,
    context: Optional[dict] = None
) -> logging.Logger:
    """
    Set up logging configuration
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        json_format: Whether to use JSON formatting
        context: Optional context dict to add to all logs
        
    Returns:
        Configured logger
    """
    
    # Create logger
    logger = logging.getLogger("data_pipeline")
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Add context filter if provided
    if context:
        context_filter = ContextFilter(context)
        for handler in logger.handlers:
            handler.addFilter(context_filter)
    
    return logger


def get_logger(
    name: str,
    level: Optional[str] = None,
    context: Optional[dict] = None
) -> logging.Logger:
    """
    Get a logger instance
    
    Args:
        name: Logger name (typically __name__)
        level: Optional logging level override
        context: Optional context to add to logs
        
    Returns:
        Logger instance
    """
    
    # Get or create logger
    logger = logging.getLogger(f"data_pipeline.{name}")
    
    # Set level if specified
    if level:
        logger.setLevel(getattr(logging, level.upper()))
    
    # Add context filter if provided
    if context:
        context_filter = ContextFilter(context)
        for handler in logger.handlers:
            handler.addFilter(context_filter)
    
    return logger


def log_with_context(logger: logging.Logger, level: str, message: str, **kwargs):
    """
    Log a message with additional context
    
    Args:
        logger: Logger instance
        level: Log level (info, warning, error, etc.)
        message: Log message
        **kwargs: Additional context fields
    """
    
    # Create log record
    log_method = getattr(logger, level.lower())
    
    # Add extra fields to record
    extra = {"extra_fields": kwargs}
    log_method(message, extra=extra)


# Initialize default logger
default_logger = setup_logging(
    level="INFO",
    log_file=None,
    json_format=False
)
