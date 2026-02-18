import json
import typing as t
from email.parser import BytesParser
from email.policy import default

import httpx


class FakeOpenAIAPI:
    """
    Emulate the subset of OpenAI batch endpoints used in tests.
    """

    def __init__(self) -> None:
        self._files: dict[str, list[dict[str, t.Any]]] = {}
        self._batches: dict[str, dict[str, str]] = {}
        self._batch_poll_count: dict[str, int] = {}
        self._counter = 0

    def _json_response(self, *, status_code: int, payload: dict[str, t.Any]) -> httpx.Response:
        """
        Build a JSON response for the mock API.

        Parameters
        ----------
        status_code : int
            HTTP status code.
        payload : dict[str, typing.Any]
            JSON payload to return.

        Returns
        -------
        httpx.Response
            Response object with JSON content.
        """
        return httpx.Response(status_code=status_code, json=payload)

    def _next_id(self, *, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter}"

    def _read_request_body(self, *, request: httpx.Request) -> bytes:
        if hasattr(request, "read"):
            return request.read()
        return t.cast(bytes, request.content)

    def _parse_multipart_file(self, *, request: httpx.Request) -> list[dict[str, t.Any]]:
        """
        Parse multipart payload and extract JSONL lines from the file part.

        Parameters
        ----------
        request : httpx.Request
            Incoming HTTP request.

        Returns
        -------
        list[dict[str, typing.Any]]
            JSONL line objects from the uploaded file.
        """
        content_type = request.headers.get("content-type", "")
        body = self._read_request_body(request=request)
        message = BytesParser(policy=default).parsebytes(
            text=b"Content-Type: " + content_type.encode("utf-8") + b"\r\n\r\n" + body
        )
        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue
            name = part.get_param("name", header="content-disposition")
            if name != "file":
                continue
            payload = part.get_payload(decode=True)
            if not isinstance(payload, (bytes, str)):
                payload = b""
            return self._parse_jsonl_payload(payload=payload)
        return []

    def _parse_jsonl_payload(self, *, payload: bytes | str) -> list[dict[str, t.Any]]:
        """
        Parse a JSONL payload into list of dicts.

        Parameters
        ----------
        payload : bytes | str
            JSONL payload from multipart upload.

        Returns
        -------
        list[dict[str, typing.Any]]
            Parsed JSONL entries.
        """
        payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
        lines = [
            json.loads(s=line)
            for line in payload_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]
        return lines

    def _extract_uploaded_jsonl(self, *, request: httpx.Request) -> list[dict[str, t.Any]]:
        """
        Extract JSONL entries from an uploaded multipart file.

        Parameters
        ----------
        request : httpx.Request
            Incoming HTTP request.

        Returns
        -------
        list[dict[str, typing.Any]]
            Parsed JSONL entries.
        """
        return self._parse_multipart_file(request=request)

    def _results_for_file(self, *, file_id: str) -> str:
        requests = self._files.get(file_id, [])
        lines = []
        for request in requests:
            lines.append(
                json.dumps(
                    obj={
                        "custom_id": request["custom_id"],
                        "response": {
                            "status_code": 200,
                            "body": {
                                "model": "gpt-test",
                                "choices": [
                                    {"message": {"content": "ok"}},
                                ],
                            },
                        },
                    }
                )
            )
        return "\n".join(lines)

    def _handle_upload(self, *, request: httpx.Request) -> httpx.Response:
        """
        Handle file upload requests.

        Parameters
        ----------
        request : httpx.Request
            Incoming HTTP request.

        Returns
        -------
        httpx.Response
            Upload response.
        """
        file_id = self._next_id(prefix="file")
        self._files[file_id] = self._extract_uploaded_jsonl(request=request)
        return self._json_response(status_code=200, payload={"id": file_id})

    def _handle_batch_create(self, *, request: httpx.Request) -> httpx.Response:
        """
        Handle batch creation requests.

        Parameters
        ----------
        request : httpx.Request
            Incoming HTTP request.

        Returns
        -------
        httpx.Response
            Batch creation response.
        """
        payload = json.loads(s=self._read_request_body(request=request))
        batch_id = self._next_id(prefix="batch")
        output_file_id = self._next_id(prefix="output")
        self._batches[batch_id] = {
            "input_file_id": payload["input_file_id"],
            "output_file_id": output_file_id,
        }
        self._files[output_file_id] = self._files[payload["input_file_id"]]
        return self._json_response(status_code=200, payload={"id": batch_id})

    def _handle_batch_status(self, *, batch_id: str) -> httpx.Response:
        """
        Handle batch status polling requests.

        Parameters
        ----------
        batch_id : str
            Batch identifier.

        Returns
        -------
        httpx.Response
            Batch status response.
        """
        poll_count = self._batch_poll_count.get(batch_id, 0) + 1
        self._batch_poll_count[batch_id] = poll_count
        batch_info = self._batches[batch_id]
        status = "completed" if poll_count >= 1 else "in_progress"
        return self._json_response(
            status_code=200,
            payload={
                "id": batch_id,
                "status": status,
                "output_file_id": batch_info["output_file_id"],
            },
        )

    def _handle_file_content(self, *, file_id: str) -> httpx.Response:
        """
        Handle batch result content requests.

        Parameters
        ----------
        file_id : str
            File identifier.

        Returns
        -------
        httpx.Response
            Content response.
        """
        return httpx.Response(
            status_code=200,
            text=self._results_for_file(file_id=file_id),
        )

    def handler(self, request: httpx.Request) -> httpx.Response:
        """
        Dispatch incoming requests to mock handlers.

        Parameters
        ----------
        request : httpx.Request
            Incoming HTTP request.

        Returns
        -------
        httpx.Response
            Mock response.
        """
        path = request.url.path
        if request.method == "POST" and path == "/v1/files":
            return self._handle_upload(request=request)

        if request.method == "POST" and path == "/v1/batches":
            return self._handle_batch_create(request=request)

        if request.method == "GET" and path.startswith("/v1/batches/"):
            batch_id = path.split("/")[-1]
            return self._handle_batch_status(batch_id=batch_id)

        if request.method == "GET" and path.startswith("/v1/files/") and path.endswith("/content"):
            file_id = path.split("/")[-2]
            return self._handle_file_content(file_id=file_id)

        return self._json_response(status_code=404, payload={"error": "not found"})


def make_openai_batch_transport() -> httpx.MockTransport:
    """
    Create a mock OpenAI batch transport for tests.

    Returns
    -------
    httpx.MockTransport
        Mock transport that emulates file upload, batch creation, and results retrieval.
    """
    api = FakeOpenAIAPI()
    return httpx.MockTransport(handler=api.handler)
