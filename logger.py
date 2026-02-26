"""Logging configuration for the Telegram WhatsApp bot."""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logger(name: str = "whatsapp_bot") -> logging.Logger:
    """
    Set up and return a configured logger instance.

    Args:
        name: Logger name (default: 'whatsapp_bot')

    Returns:
        Configured Logger instance
    """
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", "bot.log")

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (max 10 MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# Module-level default logger
logger = setup_logger()
