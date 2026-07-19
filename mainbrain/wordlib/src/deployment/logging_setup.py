"""
Structured JSON logging for deployment. Writes newline-delimited JSON to
logs/deployment.log so every run is auditable and machine-parseable, plus a
human-readable console line.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Attach any extra structured fields
        for k, v in getattr(record, "__dict__", {}).items():
            if k.startswith("ctx_"):
                payload[k[4:]] = v
        return json.dumps(payload, default=str)


def get_deployment_logger(root: Path) -> logging.Logger:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("deployment")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()  # avoid duplicate handlers on re-init

    # JSON file handler
    fh = logging.FileHandler(log_dir / "deployment.log", encoding="utf-8")
    fh.setFormatter(JsonLineFormatter())
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    return logger
