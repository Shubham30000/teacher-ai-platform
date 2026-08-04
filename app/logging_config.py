"""
Application-wide logging configuration.

Call ``configure_logging()`` once, at process startup (``app.main``
does this on import). Every module then does::

    import logging
    logger = logging.getLogger(__name__)

which inherits this configuration automatically - no module should
call ``logging.basicConfig`` itself.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import get_settings

_CONFIGURED = False

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """Idempotently configure the root logger with console + rotating file handlers."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    log_dir = Path(settings.upload_dir).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level.upper())
    root_logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Quiet noisy third-party loggers unless we're in debug mode.
    if not settings.debug:
        for noisy in ("httpx", "httpcore", "chromadb", "urllib3", "PIL"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True
