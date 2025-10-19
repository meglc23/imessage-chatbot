#!/usr/bin/env python3
"""
Centralized logging system for iMessage chatbot.
"""

import os
from datetime import datetime
from typing import Optional


def _write_log(level: str, message: str, log_file: Optional[str] = None):
    """
    Internal function to write log messages with timestamp and level.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        message: Log message
        log_file: Optional custom log file path. If None, uses date-based partitioning.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Use date-based log file if not specified
    if log_file is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = f"data/logs/bot_log_{date_str}.txt"

    try:
        # Ensure logs directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Write log entry
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {level:7} | {message}\n")
    except Exception as e:
        # Silently fail - logging should never crash the application
        print(f"Warning: Failed to write log: {e}")


def log_debug(message: str, log_file: Optional[str] = None):
    """
    Log debug message (detailed information for diagnosing issues).

    Args:
        message: Debug message
        log_file: Optional custom log file path

    Example:
        log_debug("Processing 25 messages for context")
    """
    _write_log("DEBUG", message, log_file)


def log_info(message: str, log_file: Optional[str] = None):
    """
    Log info message (general informational messages about application progress).

    Args:
        message: Info message
        log_file: Optional custom log file path

    Example:
        log_info("Startup: Retrieved 30 messages for bootstrap")
    """
    _write_log("INFO", message, log_file)


def log_warning(message: str, log_file: Optional[str] = None):
    """
    Log warning message (potentially harmful situations).

    Args:
        message: Warning message
        log_file: Optional custom log file path

    Example:
        log_warning("API rate limit approaching")
    """
    _write_log("WARNING", message, log_file)


def log_error(message: str, log_file: Optional[str] = None):
    """
    Log error message (error events that might still allow the app to continue).

    Args:
        message: Error message
        log_file: Optional custom log file path

    Example:
        log_error(f"Failed to send message: {error}")
    """
    _write_log("ERROR", message, log_file)


def log_message(message: str, log_file: Optional[str] = None):
    """
    Log general message (alias for log_info, for backward compatibility).

    Args:
        message: Log message
        log_file: Optional custom log file path

    Example:
        log_message("Bot started successfully")
    """
    log_info(message, log_file)
