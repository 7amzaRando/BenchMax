"""Centralized logging configuration for BenchMax.

Provides both human-readable and JSON structured logging so that:
- Humans get readable terminal output with context prefixes
- Agents/CI get parseable JSON lines via --json-logs or BENCHMAX_JSON_LOGS=true

Usage from main.py:
    from backend.logging_setup import configure_logging
    configure_logging()

Environment variables:
    BENCHMAX_LOG_LEVEL  — root log level (default: INFO)
    BENCHMAX_LOG_FILE   — path to log file (default: records/benchmax.log)
    BENCHMAX_JSON_LOGS  — set to "true" for JSON structured output
"""
import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line — parseable by agents and CI."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge LoggerAdapter extras (run_id, benchmark, etc.)
        for key in ("run_id", "benchmark", "model", "task_id"):
            val = getattr(record, key, None)
            if val is not None:
                entry[key] = val
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


class _HumanFormatter(logging.Formatter):
    """Human-readable with context prefixes: [run_id=213 benchmark=Aider Polyglot]"""

    def format(self, record: logging.LogRecord) -> str:
        parts = [self.formatTime(record, "%Y-%m-%d %H:%M:%S")]
        parts.append(f"[{record.levelname}]")
        # Append context extras as bracketed key=value pairs
        context = []
        for key in ("run_id", "benchmark", "model", "task_id"):
            val = getattr(record, key, None)
            if val is not None:
                context.append(f"{key}={val}")
        if context:
            parts.append(f"[{' '.join(context)}]")
        parts.append(f"{record.name}: {record.getMessage()}")
        if record.exc_info and record.exc_info[0]:
            parts.append(self.formatException(record.exc_info))
        return " ".join(parts)


def configure_logging():
    """Set up root logger with console + rotating file handlers.

    Called once from main.py. Subsequent calls are no-ops (basicConfig is
    idempotent).
    """
    level_name = os.environ.get("BENCHMAX_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    use_json = os.environ.get("BENCHMAX_JSON_LOGS", "").lower() in ("1", "true", "yes")
    formatter = _JsonFormatter() if use_json else _HumanFormatter()

    # Console handler (stderr)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)

    # Rotating file handler (records/benchmax.log)
    log_file = os.environ.get("BENCHMAX_LOG_FILE", "")
    if not log_file:
        root = Path(__file__).parent.parent
        log_dir = root / "records"
        log_dir.mkdir(exist_ok=True)
        log_file = str(log_dir / "benchmax.log")

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    # File handler always gets JSON for machine parsing
    file_handler.setFormatter(_JsonFormatter())

    logging.basicConfig(
        level=level,
        format="%(message)s",  # formatter handles everything
        handlers=[console, file_handler],
        force=True,  # override any prior basicConfig (e.g. benchmax_server.py)
    )
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
