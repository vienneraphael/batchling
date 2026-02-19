"""
Batchling-specific runtime exceptions.
"""


class DeferredExit(RuntimeError):
    """
    Signal that deferred mode stopped active polling for this runtime.

    Notes
    -----
    This exception is raised intentionally to stop caller execution flow when
    deferred idle conditions are met.
    """
