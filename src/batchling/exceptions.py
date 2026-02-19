"""
Batchling-specific runtime exceptions.
"""

from __future__ import annotations

import typing as t

DEFERRED_RESPONSE_HEADER = "x-batchling-deferred"


class DeferredExit(RuntimeError):
    """
    Signal that deferred mode stopped active polling for this runtime.

    Notes
    -----
    This exception is raised intentionally to stop caller execution flow when
    deferred idle conditions are met.
    """


def is_deferred_exit_error(*, error: BaseException) -> bool:
    """
    Detect whether an exception chain was caused by deferred-mode early exit.

    Parameters
    ----------
    error : BaseException
        Top-level exception to inspect.

    Returns
    -------
    bool
        ``True`` when the exception or any nested cause/context indicates
        deferred-mode early exit.
    """
    seen: set[int] = set()
    to_visit: list[BaseException] = [error]
    while to_visit:
        current = to_visit.pop()
        current_id = id(current)
        if current_id in seen:
            continue
        seen.add(current_id)

        if isinstance(current, DeferredExit):
            return True

        response = getattr(current, "response", None)
        headers = getattr(response, "headers", None)
        if headers is not None and t.cast(str, headers.get(DEFERRED_RESPONSE_HEADER, "0")) == "1":
            return True

        cause = getattr(current, "__cause__", None)
        if isinstance(cause, BaseException):
            to_visit.append(cause)
        context = getattr(current, "__context__", None)
        if isinstance(context, BaseException):
            to_visit.append(context)

    return False
