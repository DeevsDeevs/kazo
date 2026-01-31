import json
import logging

from kazo.logging import JSONFormatter, setup_logging


def test_json_formatter_basic():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="kazo.test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    output = json.loads(formatter.format(record))
    assert output["level"] == "INFO"
    assert output["message"] == "hello world"
    assert output["logger"] == "kazo.test"
    assert "timestamp" in output
    assert "chat_id" not in output


def test_json_formatter_extra_fields():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="kazo.test",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="test",
        args=(),
        exc_info=None,
    )
    record.chat_id = 12345
    record.user_id = 67890
    record.handler = "receipt"
    record.latency_ms = 150.5
    output = json.loads(formatter.format(record))
    assert output["chat_id"] == 12345
    assert output["user_id"] == 67890
    assert output["handler"] == "receipt"
    assert output["latency_ms"] == 150.5


def test_json_formatter_exception():
    formatter = JSONFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = logging.LogRecord(
            name="kazo.test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="failed",
            args=(),
            exc_info=sys.exc_info(),
        )
    output = json.loads(formatter.format(record))
    assert "exception" in output
    assert "ValueError: boom" in output["exception"]


def test_setup_logging():
    setup_logging(level=logging.DEBUG)
    root = logging.getLogger()
    assert root.level == logging.DEBUG
    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0].formatter, JSONFormatter)
    # Cleanup
    root.handlers.clear()
    logging.basicConfig(level=logging.WARNING)
