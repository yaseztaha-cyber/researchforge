"""Structured logging: every research run carries research_run_id; never log secrets."""

from __future__ import annotations

import json
import logging
import sys
import time
from typing import Any


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    root = logging.getLogger("researchforge")
    root.handlers = [handler]
    root.setLevel(level)
    root.propagate = False
    return root


logger = setup_logging()


def log_event(event: str, *, run_id: str = "-", stage: str = "-", status: str = "info", **fields: Any) -> None:
    payload = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        "research_run_id": run_id,
        "stage": stage,
        "status": status,
        **{k: v for k, v in fields.items() if "key" not in k.lower() and "secret" not in k.lower()},
    }
    logger.info(json.dumps(payload))
