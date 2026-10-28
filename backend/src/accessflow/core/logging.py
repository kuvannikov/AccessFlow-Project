"""One allowlisted, single-line HTTP record per request."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

REQUEST_ID_ATTRIBUTE = "_accessflow_request_id"

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
http_logger = logging.getLogger("accessflow.http")


class HttpFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, UTC).isoformat()
        values = {
            "time": timestamp,
            "level": record.levelname,
            "request_id": getattr(record, "request_id", "-"),
            "method": getattr(record, "method", "OTHER"),
            "route": getattr(record, "route", "unmatched"),
            "status": getattr(record, "status", 500),
            "duration_ms": getattr(record, "duration_ms", 0),
        }
        for key in ("error", "origin"):
            if hasattr(record, key):
                values[key] = getattr(record, key)
        return " ".join(f"{key}={json.dumps(value)}" for key, value in values.items())


class ServerErrorFilter(logging.Filter):
    """Keep server diagnostics from serializing application exceptions."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            request_id = getattr(record.exc_info[1], REQUEST_ID_ATTRIBUTE, "-")
            record.msg = f"event=server_error request_id={json.dumps(request_id)}"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        return True


def configure_logging() -> None:
    # Uvicorn's default access logger includes raw paths and query strings.
    logging.getLogger("uvicorn.access").disabled = True
    server_logger = logging.getLogger("uvicorn.error")
    if not any(isinstance(item, ServerErrorFilter) for item in server_logger.filters):
        server_logger.addFilter(ServerErrorFilter())
    http_logger.setLevel(logging.INFO)
    http_logger.propagate = False
    if not any(handler.get_name() == "accessflow_http" for handler in http_logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(HttpFormatter())
        handler.set_name("accessflow_http")
        http_logger.addHandler(handler)
