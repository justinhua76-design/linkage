"""Logging configuration with PHI protection.

Policy: application logs may contain request ids, route templates, status
codes, durations, resource ids (UUIDs) and error *codes*. They must never
contain patient identifiers, lab values, ages or request bodies.

Enforcement is two-fold:
1. Code never passes such data to the logger (only codes / ids).
2. ``PhiRedactionFilter`` is a safety net: log records may only carry
   whitelisted ``extra`` keys and numeric literals in the rendered message
   are masked, so accidental ``logger.info(f"... {value}")`` cannot leak lab values.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime

ALLOWED_EXTRA_KEYS = {
    "request_id",
    "method",
    "route",
    "status_code",
    "duration_ms",
    "actor",
    "role",
    "event",
    "error_codes",
    "resource_type",
    "resource_id",
}

_STD_ATTRS = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime", "taskName"}
_UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_NUM_RE = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?(?![\w.])")


def _mask_numbers(text: str) -> str:
    # keep UUIDs intact, mask free-standing numbers
    uuids: list[str] = []

    def keep(m: re.Match[str]) -> str:
        uuids.append(m.group(0))
        return f"\x00{len(uuids) - 1}\x00"

    tmp = _UUID_RE.sub(keep, text)
    tmp = _NUM_RE.sub("[redacted]", tmp)
    return re.sub("\x00(\\d+)\x00", lambda m: uuids[int(m.group(1))], tmp)


class PhiRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Drop non-whitelisted extras
        for key in list(vars(record).keys()):
            if key not in _STD_ATTRS and key not in ALLOWED_EXTRA_KEYS:
                delattr(record, key)
        # Render and mask numbers in the message; never keep raw args
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            msg = str(record.msg)
        record.msg = _mask_numbers(msg)
        record.args = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ALLOWED_EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info and record.exc_info[0] is not None:
            # exception type only - tracebacks may embed local variable values
            payload["exc_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(PhiRedactionFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # uvicorn's access log prints full query strings; we emit our own access log.
    logging.getLogger("uvicorn.access").disabled = True
    for name in ("uvicorn", "uvicorn.error", "sqlalchemy.engine"):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
    logging.getLogger("sqlalchemy.engine").setLevel("WARNING")  # never log SQL params
