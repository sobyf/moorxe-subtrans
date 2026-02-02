import logging
import sys


def setup_logger(name: str) -> logging.Logger:
    """
    Creates and configures a reusable application logger.

    Features:
    - Unified log format
    - Stream output to stdout (Docker-friendly)
    - Prevents duplicate handlers
    - Supports multiple module loggers

    Args:
        name (str): Logger name (usually module or service name)

    Returns:
        logging.Logger: Configured logger instance
    """

    logger = logging.getLogger(name)

    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Create console handler (stdout is preferred for containers)
    handler = logging.StreamHandler(sys.stdout)

    # Production-friendly log format
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
