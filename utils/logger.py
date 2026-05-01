"""
Logging configuration.

Convention: library/runtime modules use ``logging.getLogger(__name__)`` (or
``setup_logger`` for the main worker). Scripts under ``scripts/`` and small CLI
helpers may use ``print`` for human-readable PASS/FAIL output.

Optional **structured JSON** lines (Milestone J1): set env ``STRUCTURED_JSON_LOGGING``
to ``1`` / ``true`` / ``yes`` and call ``maybe_install_structured_json_handler()``
once at worker startup (e.g. start of ``run_scanner``). Emits one JSON object per
log record on the ``trend_scanner`` logger in addition to existing formatting.
"""

import datetime
import json
import logging
import os
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

_structured_json_installed = False


class SafeStreamHandler(logging.StreamHandler):
    """Stream handler that degrades unsupported Unicode safely."""

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            payload = msg + self.terminator

            try:
                stream.write(payload)
            except UnicodeEncodeError:
                encoding = getattr(stream, 'encoding', None) or 'utf-8'
                safe_bytes = payload.encode(encoding, errors='replace')

                if hasattr(stream, 'buffer'):
                    stream.buffer.write(safe_bytes)
                else:
                    stream.write(safe_bytes.decode(encoding, errors='replace'))

            self.flush()
        except Exception:
            self.handleError(record)


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime_iso_from_record(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def datetime_iso_from_record(record: logging.LogRecord) -> str:
    dt = datetime.datetime.fromtimestamp(record.created, tz=datetime.timezone.utc)
    return dt.isoformat(timespec="milliseconds")


def maybe_install_structured_json_handler() -> None:
    """If STRUCTURED_JSON_LOGGING is set, add a JSON-lines handler to ``trend_scanner``."""
    global _structured_json_installed
    if _structured_json_installed:
        return
    flag = os.getenv("STRUCTURED_JSON_LOGGING", "").strip().lower()
    if flag not in ("1", "true", "yes", "on"):
        return
    _structured_json_installed = True
    worker = logging.getLogger("trend_scanner")
    handler = SafeStreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    handler.setFormatter(_JsonLineFormatter())
    worker.addHandler(handler)


def setup_logger(name: str = None, log_file: str = None) -> logging.Logger:
    """
    Set up a logger with console and file handlers
    
    Args:
        name: Logger name (if None, returns root logger)
        log_file: Path to log file (if None, uses default)
    
    Returns:
        Configured logger instance
    """
    # Get or create logger
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter('%(message)s')
    
    # Console handler
    console = SafeStreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(simple_formatter)
    logger.addHandler(console)
    
    # File handler (if log_file specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
    
    return logger

# Default application logger
app_logger = setup_logger('trend_scanner', 'trend_scanner.log')