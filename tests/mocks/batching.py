import json
import typing as t
from email.parser import BytesParser
from email.policy import default
from urllib.parse import unquote

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
        total_requests = len(self._files.get(batch_info["input_file_id"], []))
        completed_requests = total_requests if status == "completed" else 0
        return self._json_response(
            status_code=200,
            payload={
                "id": batch_id,
                "status": status,
                "request_counts": {"completed": completed_requests},
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


class FakeVertexAPI:
    """
    Emulate the subset of Vertex and GCS endpoints used in tests.
    """

    def __init__(self) -> None:
        self._gcs_objects: dict[tuple[str, str], str] = {}
        self._jobs: dict[str, dict[str, t.Any]] = {}
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

    def _parse_jsonl_payload(self, *, payload: bytes | str) -> list[dict[str, t.Any]]:
        payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
        return [
            json.loads(s=line)
            for line in payload_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]

    def _handle_gcs_upload(self, *, request: httpx.Request) -> httpx.Response:
        bucket = request.url.path.split("/")[5]
        object_name = unquote(string=request.url.params["name"])
        payload = self._read_request_body(request=request).decode("utf-8")
        self._gcs_objects[(bucket, object_name)] = payload
        return self._json_response(
            status_code=200,
            payload={"bucket": bucket, "name": object_name},
        )

    def _build_prediction_row(self, *, request_row: dict[str, t.Any]) -> dict[str, t.Any]:
        request_payload = request_row["request"]
        response = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"text": "ok"}],
                    }
                }
            ],
            "modelVersion": "gemini-test",
        }
        if request_payload.get("force_error"):
            return {
                "key": request_row["key"],
                "status": {
                    "code": 13,
                    "message": "forced failure",
                },
            }
        return {
            "key": request_row["key"],
            "response": response,
        }

    def _store_job_results(
        self,
        *,
        bucket: str,
        output_prefix: str,
        request_rows: list[dict[str, t.Any]],
    ) -> tuple[str, int, int]:
        predictions: list[str] = []
        errors: list[str] = []
        for request_row in request_rows:
            result_row = self._build_prediction_row(request_row=request_row)
            encoded = json.dumps(obj=result_row)
            if "response" in result_row:
                predictions.append(encoded)
            else:
                errors.append(encoded)

        output_directory = f"gs://{bucket}/{output_prefix}/prediction-model-0001-of-0001"
        prediction_prefix = f"{output_prefix}/prediction-model-0001-of-0001"
        if predictions:
            midpoint = max(1, len(predictions) // 2)
            prediction_chunks = [predictions[:midpoint], predictions[midpoint:]]
            for index, chunk in enumerate(prediction_chunks, start=1):
                if not chunk:
                    continue
                object_name = f"{prediction_prefix}/predictions_{index:04d}.jsonl"
                self._gcs_objects[(bucket, object_name)] = "\n".join(chunk)
        if errors:
            object_name = f"{prediction_prefix}/errors_0001.jsonl"
            self._gcs_objects[(bucket, object_name)] = "\n".join(errors)

        return output_directory, len(predictions), len(errors)

    def _handle_batch_create(self, *, request: httpx.Request) -> httpx.Response:
        payload = json.loads(s=self._read_request_body(request=request))
        input_uri = payload["inputConfig"]["gcsSource"]["uris"][0]
        output_uri_prefix = payload["outputConfig"]["gcsDestination"]["outputUriPrefix"]

        input_bucket, input_object_name = input_uri[5:].split("/", 1)
        request_rows = self._parse_jsonl_payload(
            payload=self._gcs_objects[(input_bucket, input_object_name)]
        )
        output_bucket, output_prefix = output_uri_prefix[5:].split("/", 1)
        output_directory, successful_count, failed_count = self._store_job_results(
            bucket=output_bucket,
            output_prefix=output_prefix,
            request_rows=request_rows,
        )

        job_name = request.url.path.removeprefix("/v1/") + "/" + self._next_id(prefix="batch")
        self._jobs[job_name] = {
            "state": "JOB_STATE_SUCCEEDED",
            "output_directory": output_directory,
            "successful_count": successful_count,
            "failed_count": failed_count,
        }
        return self._json_response(
            status_code=200,
            payload={"name": job_name},
        )

    def _handle_batch_status(self, *, request: httpx.Request) -> httpx.Response:
        job_name = request.url.path.removeprefix("/v1/").removeprefix("/v1beta1/")
        job = self._jobs[job_name]
        return self._json_response(
            status_code=200,
            payload={
                "name": job_name,
                "state": job["state"],
                "completionStats": {
                    "successfulCount": job["successful_count"],
                    "failedCount": job["failed_count"],
                },
                "outputInfo": {
                    "gcsOutputDirectory": job["output_directory"],
                },
            },
        )

    def _handle_gcs_list(self, *, request: httpx.Request) -> httpx.Response:
        bucket = request.url.path.split("/")[4]
        prefix = request.url.params.get("prefix", "")
        items = [
            {"name": object_name}
            for current_bucket, object_name in sorted(self._gcs_objects.keys())
            if current_bucket == bucket and object_name.startswith(prefix)
        ]
        return self._json_response(status_code=200, payload={"items": items})

    def _handle_gcs_download(self, *, request: httpx.Request) -> httpx.Response:
        bucket = request.url.path.split("/")[4]
        object_name = unquote(string=request.url.path.split("/o/", 1)[1])
        return httpx.Response(
            status_code=200,
            text=self._gcs_objects[(bucket, object_name)],
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
        if (
            request.url.host == "storage.googleapis.com"
            and request.method == "POST"
            and request.url.path.startswith("/upload/storage/v1/b/")
        ):
            return self._handle_gcs_upload(request=request)

        if (
            request.url.host == "storage.googleapis.com"
            and request.method == "GET"
            and request.url.path.startswith("/storage/v1/b/")
            and request.url.path.endswith("/o")
        ):
            return self._handle_gcs_list(request=request)

        if (
            request.url.host == "storage.googleapis.com"
            and request.method == "GET"
            and request.url.path.startswith("/storage/v1/b/")
            and "/o/" in request.url.path
            and request.url.params.get("alt") == "media"
        ):
            return self._handle_gcs_download(request=request)

        if (
            request.url.host.endswith("-aiplatform.googleapis.com")
            and request.method == "POST"
            and request.url.path.endswith("/batchPredictionJobs")
        ):
            return self._handle_batch_create(request=request)

        if (
            request.url.host.endswith("-aiplatform.googleapis.com")
            and request.method == "GET"
            and "/batchPredictionJobs/" in request.url.path
        ):
            return self._handle_batch_status(request=request)

        return self._json_response(status_code=404, payload={"error": "not found"})


def make_vertex_batch_transport() -> httpx.MockTransport:
    """
    Create a mock Vertex batch transport for tests.

    Returns
    -------
    httpx.MockTransport
        Mock transport that emulates GCS staging, batch creation, polling, and result download.
    """
    api = FakeVertexAPI()
    return httpx.MockTransport(handler=api.handler)
