import logging
import sys
import traceback
from contextvars import ContextVar

from app.config import settings

request_id: ContextVar[str] = ContextVar("request_id", default="-")
logger = logging.getLogger("accessflow")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id.get()
        return True


class SafeFormatter(logging.Formatter):
    def formatException(self, exc_info: tuple) -> str:
        exception_type, _, stack = exc_info
        return f"{exception_type.__name__}\n{''.join(traceback.format_tb(stack))}"


def configure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        SafeFormatter("%(asctime)s %(levelname)s request_id=%(request_id)s %(message)s")
    )
    logger.addHandler(handler)
    logger.setLevel(settings.log_level)
    logger.propagate = False
