"""Public exceptions exposed by batchling."""

from __future__ import annotations


class DryRunEarlyExit(RuntimeError):
    """
    Raised when dry-run mode exits before returning a provider response.

    Parameters
    ----------
    source : str
        Dry-run branch that produced the early exit.
    provider : str
        Provider name.
    endpoint : str
        Endpoint key.
    model : str
        Model key.
    batch_id : str
        Simulated batch identifier.
    custom_id : str
        Request custom identifier.
    """

    def __init__(
        self,
        *,
        source: str,
        provider: str,
        endpoint: str,
        model: str,
        batch_id: str,
        custom_id: str,
    ) -> None:
        self.source = source
        self.provider = provider
        self.endpoint = endpoint
        self.model = model
        self.batch_id = batch_id
        self.custom_id = custom_id
        message = (
            "Dry run early exit triggered for "
            f"{provider}:{endpoint}:{model} (batch_id={batch_id}, custom_id={custom_id}, source={source})"
        )
        super().__init__(message)
