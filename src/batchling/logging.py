import logging
import typing as t

_DROP_LOG_FIELDS = frozenset(
    {
        "body",
        "content",
        "data",
        "files",
        "headers",
        "json",
        "payload",
        "result_item",
    }
)


def setup_logging() -> None:
    """
    Configure package logger defaults.
    """
    logging.getLogger(name="batchling").setLevel(level=logging.WARNING)


def _format_log_message(*, event: str, **context: t.Any) -> str:
    """
    Build a compact key/value log message.

    Parameters
    ----------
    event : str
        Log event summary.
    **context : typing.Any
        Optional context values.

    Returns
    -------
    str
        Formatted message.
    """
    parts = [event]
    filtered_context = {
        key: value
        for key, value in context.items()
        if value is not None and key not in _DROP_LOG_FIELDS
    }
    if filtered_context:
        context_fields = " ".join(f"{key}={value}" for key, value in filtered_context.items())
        parts.append(context_fields)
    return " | ".join(parts)


def log_debug(*, logger: logging.Logger, event: str, **context: t.Any) -> None:
    """
    Emit a debug log with normalized message formatting.

    Parameters
    ----------
    logger : logging.Logger
        Target logger instance.
    event : str
        Event summary.
    **context : typing.Any
        Optional log context.
    """
    logger.debug(msg=_format_log_message(event=event, **context))


def log_info(*, logger: logging.Logger, event: str, **context: t.Any) -> None:
    """
    Emit an info log with normalized message formatting.

    Parameters
    ----------
    logger : logging.Logger
        Target logger instance.
    event : str
        Event summary.
    **context : typing.Any
        Optional log context.
    """
    logger.info(msg=_format_log_message(event=event, **context))


def log_warning(*, logger: logging.Logger, event: str, **context: t.Any) -> None:
    """
    Emit a warning log with normalized message formatting.

    Parameters
    ----------
    logger : logging.Logger
        Target logger instance.
    event : str
        Event summary.
    **context : typing.Any
        Optional log context.
    """
    logger.warning(msg=_format_log_message(event=event, **context))


def log_error(*, logger: logging.Logger, event: str, **context: t.Any) -> None:
    """
    Emit an error log with normalized message formatting.

    Parameters
    ----------
    logger : logging.Logger
        Target logger instance.
    event : str
        Event summary.
    **context : typing.Any
        Optional log context.
    """
    logger.error(msg=_format_log_message(event=event, **context))
