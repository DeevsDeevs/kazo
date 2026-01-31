import json
import logging
import traceback
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "chat_id"):
            entry["chat_id"] = record.chat_id
        if hasattr(record, "user_id"):
            entry["user_id"] = record.user_id
        if hasattr(record, "handler"):
            entry["handler"] = record.handler
        if hasattr(record, "latency_ms"):
            entry["latency_ms"] = record.latency_ms
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(entry)


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
