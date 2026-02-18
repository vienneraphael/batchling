import logging
from collections.abc import Iterator
from contextlib import contextmanager

import structlog


def setup_logging() -> None:
    logging.getLogger("batchling").setLevel(logging.DEBUG)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,  # Critical for context vars
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@contextmanager
def logging_context(**required_context) -> Iterator[None]:
    current = structlog.contextvars.get_contextvars()
    to_bind = {k: v for k, v in required_context.items() if k not in current}

    if to_bind:
        with structlog.contextvars.bound_contextvars(**to_bind):
            yield
    else:
        yield
