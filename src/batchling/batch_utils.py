import copy
import json

import httpx
from openai import NOT_GIVEN, Client, DefaultHttpxClient
from pydantic import BaseModel

from batchling.file_utils import write_jsonl_file


class CapturingTransport(httpx.BaseTransport):
    """
    A custom HTTP transport that intercepts every request, captures its details,
    and then raises an exception to abort the network call.
    """

    def __init__(self):
        self.captured_request = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        captured = {
            "method": request.method,
            "url": request.url.raw_path.decode(),
        }
        try:
            if request.content:
                captured["body"] = json.loads(request.content.decode("utf-8"))
            else:
                captured["body"] = None
        except Exception:
            captured["body"] = request.content.decode("utf-8") if request.content else None
        finally:
            self.captured_request = captured
            raise Exception("Aborted request in CapturingTransport to capture payload.")


def batch_create_chat_completion(
    custom_id: str,
    messages: list[dict],
    model: str,
    response_format: BaseModel | None = None,
) -> str | None:
    """
    Captures the full API request (as built by the SDK) when calling the beta chat
    completions parsing method. The function returns a single-line JSON string (JSONL)
    that contains:

      - custom_id: A required identifier provided by the caller.
      - method: HTTP method (e.g., "POST").
      - url: The relative endpoint (e.g., "/v1/chat/completions").
      - body: The full JSON payload built by the SDK.

    If the SDK's validation fails (for example, due to an invalid response_format),
    no request is built and an error is raised.
    """
    capturing_transport = CapturingTransport()

    custom_http_client = DefaultHttpxClient(transport=capturing_transport)

    client = Client(http_client=custom_http_client, max_retries=0)

    try:
        _ = client.beta.chat.completions.parse(
            messages=messages, model=model, response_format=response_format or NOT_GIVEN
        )
    except Exception as e:
        captured: dict | None = capturing_transport.captured_request
        if captured is None:
            raise e
        else:
            batch_request = {
                "custom_id": custom_id,
                "method": captured.get("method"),
                "url": captured.get("url"),
                "body": captured.get("body"),
            }
            return json.dumps(batch_request)


def replace_placeholders(messages: list[dict], placeholder_dict: dict) -> list[dict]:
    """Replace the placeholders in the messages

    Args:
        messages (list[dict]): The messages to replace the placeholders in
        placeholder_dict (dict): The placeholder to replace in the messages

    Returns:
        list[dict]: The messages with the placeholders replaced
    """
    messages_copy = copy.deepcopy(messages)
    for message in messages_copy:
        if message["role"] == "user":
            content = message["content"]
            if isinstance(content, str):
                message["content"] = content.format(**placeholder_dict)
            elif isinstance(content, list):
                for item in content:
                    item["text"] = item["text"].format(**placeholder_dict)
            else:
                raise ValueError(f"Invalid content type: {type(content)}")
    return messages_copy


def write_input_batch_file(
    file_path: str,
    custom_id: str,
    model: str,
    messages: list[dict],
    response_format: BaseModel | None = None,
    placeholders: list[dict] | None = None,
) -> None:
    """Create the batch file

    Args:
        model (str): The model to use
        messages (list[dict]): The messages to use
        response_model (BaseModel | None): The response model for structured output generation, if any.
        **kwargs: Additional arguments to pass to the batch_create_chat_completion function.

    Returns:
        FileObject: The batch file object
    """
    if placeholders is None:
        placeholders = []
    batch_requests = []
    for placeholder_dict in placeholders:
        clean_messages = replace_placeholders(messages=messages, placeholder_dict=placeholder_dict)
        batch_request = batch_create_chat_completion(
            custom_id=custom_id,
            messages=clean_messages,
            model=model,
            response_format=response_format,
        )
        batch_requests.append(batch_request)
    write_jsonl_file(file_path=file_path, data=batch_requests)
