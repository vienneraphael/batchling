import typing as t

from batchling.providers.base import PendingRequestLike
from batchling.providers.openai import OpenAIProvider


class GroqProvider(OpenAIProvider):
    """Provider adapter for Groq's HTTP and Batch APIs."""

    name = "groq"
    hostnames = ("api.groq.com",)
    batchable_endpoints = (
        "/openai/v1/chat/completions",
        "/openai/v1/audio/transcriptions",
        "/openai/v1/audio/translations",
    )
    file_upload_endpoint = "/openai/v1/files"
    file_content_endpoint = "/openai/v1/files/{id}/content"
    batch_endpoint = "/openai/v1/batches"

    @staticmethod
    def _strip_openai_prefix(*, path: str) -> str:
        """
        Remove Groq's OpenAI compatibility prefix from request paths.

        Parameters
        ----------
        path : str
            Request path potentially prefixed with ``/openai``.

        Returns
        -------
        str
            Canonical provider path without the ``/openai`` prefix.
        """
        if path.startswith("/openai/"):
            return path[len("/openai") :]
        return path

    def build_jsonl_lines(
        self,
        *,
        requests: t.Sequence[PendingRequestLike],
    ) -> list[dict[str, t.Any]]:
        """
        Build JSONL lines with canonical endpoint URLs for Groq batches.

        Parameters
        ----------
        requests : typing.Sequence[PendingRequestLike]
            Pending requests to serialize.

        Returns
        -------
        list[dict[str, typing.Any]]
            JSONL lines with ``url`` normalized to ``/v1/...``.
        """
        jsonl_lines = super().build_jsonl_lines(requests=requests)
        for line in jsonl_lines:
            line["url"] = self._strip_openai_prefix(path=line["url"])
        return jsonl_lines

    async def build_file_based_batch_payload(
        self,
        *,
        file_id: str,
        endpoint: str,
        queue_key: tuple[str, str, str],
    ) -> dict[str, t.Any]:
        """
        Build Groq batch payload using canonical endpoint paths.

        Parameters
        ----------
        file_id : str
            Uploaded provider file ID.
        endpoint : str
            Queue endpoint path.
        queue_key : tuple[str, str, str]
            Queue identity tuple.

        Returns
        -------
        dict[str, typing.Any]
            File-based batch payload with normalized endpoint.
        """
        return await super().build_file_based_batch_payload(
            file_id=file_id,
            endpoint=self._strip_openai_prefix(path=endpoint),
            queue_key=queue_key,
        )
