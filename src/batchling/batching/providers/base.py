class BaseProvider:
    """Interface for mapping HTTP requests to/from Batch API formats."""

    def matches_url(self, url: str) -> bool: ...

    def to_batch_item(self, method, url, headers, body) -> dict:
        """Convert HTTP request to Provider's Batch JSONL format."""

    def from_batch_result(self, result_item) -> httpx.Response:
        """Convert Provider's Batch result JSON back to HTTP Response."""
