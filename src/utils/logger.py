"""
Structured logging for DPLUS Dashboard.
Provides consistent error logging with context.
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any
import traceback


# Logs directory
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """Configure structured logging for the dashboard."""
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)

    logger = logging.getLogger('dplus')
    logger.setLevel(log_level)

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # File handler - daily log file
    today = datetime.now().strftime('%Y-%m-%d')
    log_file = os.path.join(LOGS_DIR, f'dplus_{today}.log')

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(log_level)

    # Console handler for errors
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.ERROR)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Global logger instance
_logger: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = setup_logging()
    return _logger


def log_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """Log an error with optional context."""
    logger = get_logger()

    context_str = ""
    if context:
        context_str = " | " + " | ".join(f"{k}={v}" for k, v in context.items())

    logger.error(f"{type(error).__name__}: {error}{context_str}")
    logger.debug(traceback.format_exc())


def log_warning(message: str, context: Optional[Dict[str, Any]] = None) -> None:
    """Log a warning with optional context."""
    logger = get_logger()

    context_str = ""
    if context:
        context_str = " | " + " | ".join(f"{k}={v}" for k, v in context.items())

    logger.warning(f"{message}{context_str}")


def log_info(message: str, context: Optional[Dict[str, Any]] = None) -> None:
    """Log info with optional context."""
    logger = get_logger()

    context_str = ""
    if context:
        context_str = " | " + " | ".join(f"{k}={v}" for k, v in context.items())

    logger.info(f"{message}{context_str}")


def log_data_load(filename: str, rows: int, status: str = "success") -> None:
    """Log data loading events."""
    logger = get_logger()
    logger.info(f"Data load | {filename} | {rows} rows | {status}")


class DataLoadError(Exception):
    """Custom exception for data loading errors."""
    def __init__(self, message: str, filename: Optional[str] = None, original_error: Optional[Exception] = None):
        self.message = message
        self.filename = filename
        self.original_error = original_error
        super().__init__(self.message)


class QueryError(Exception):
    """Custom exception for database query errors."""
    def __init__(self, message: str, query: Optional[str] = None, original_error: Optional[Exception] = None):
        self.message = message
        self.query = query
        self.original_error = original_error
        super().__init__(self.message)
