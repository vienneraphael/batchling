# Provider adapters

Providers translate between ordinary HTTP requests and provider-specific batch APIs. They
are responsible for URL matching and for reconstructing `httpx.Response` objects from
batch results.

## Responsibilities

- Declare supported hostnames.
- Declare explicit batchable HTTP endpoints (`path`) for hook routing.
- Declare provider-specific terminal batch states used by the core poller.
- Identify whether a URL belongs to a provider.
- Submit provider batches via `process_batch()` (upload/create job as needed).
- Consume `queue_key` context in `process_batch()` for queue-scoped behaviors
  (strictly provider + endpoint + model).
- Normalize request URLs for provider batch endpoints.
- Convert JSONL batch result lines into `httpx.Response` objects for callers.

## Registry and lookup

- Providers are auto-discovered from `batchling/batching/providers/*.py` files
  (excluding `__init__.py` and `base.py`).
- `get_provider_for_batch_request()` resolves a provider only when the request's
  `POST + path` is explicitly batchable for that provider.

## OpenAI provider

The OpenAI provider implements:

- `build_api_headers()` for auth + provider-specific passthrough headers.
- `process_batch()` to upload JSONL input and create `/v1/batches` jobs.
  It normalizes host-only values (for example, `api.openai.com`) to `https://` URLs.
  The method receives the queue key for the drained batch.
- `from_batch_result()` to decode batch output lines.

## Mistral provider

The Mistral provider reuses the OpenAI-like flow and keeps queue-derived endpoint/model
context for payload construction:

- `hostnames = ("api.mistral.ai",)`
- `batch_endpoint = "/v1/batch/jobs"`
- `file_upload_endpoint = "/v1/files"`
- `file_content_endpoint = "/v1/files"`

## Together provider

The Together provider follows the same batch lifecycle with provider-specific upload and
batch response shapes:

- `hostnames = ("api.together.xyz",)`
- `batchable_endpoints = ("/v1/chat/completions", "/v1/audio/transcriptions")`
- `file_upload_endpoint = "/v1/files/upload"`
- `file_content_endpoint = "/v1/files"`
- overrides batch file upload form fields (`file_name`, `purpose=batch-api`)
- extracts batch id from nested response payload (`job.id`)

## Doubleword provider

The Doubleword provider reuses the OpenAI provider implementation and only changes:

- `hostnames = ("api.doubleword.ai",)`
- `batchable_endpoints = ("/v1/chat/completions",)`

Terminal states are inherited unchanged from the OpenAI provider.

Common helpers now live on `BaseProvider` and can be reused by all providers:

- `matches_url()`
- `is_batchable_request()`
- `normalize_url()`
- `extract_base_and_endpoint()`
- `build_jsonl_lines()`
- `encode_body()`

Provider configuration on `BaseProvider` includes:

- `hostnames`
- `batch_method`
- `batchable_endpoints`
- `file_upload_endpoint` (where JSONL input files are uploaded)
- `file_content_endpoint` (where output/error file content is fetched)
- `terminal_states` (statuses that stop polling and trigger result resolution)

## Extension notes

- Add new provider classes by subclassing `BaseProvider` in a new module under
  `src/batchling/batching/providers/`.
- Implement `process_batch()`, `build_api_headers()`, and `from_batch_result()`.
- Use `queue_key` as the source of truth for endpoint/model context.
- Define `terminal_states` for the provider so `Batcher` can stop polling at the
  correct lifecycle states.
- Keep `matches_url()` conservative if you override it.

## Code reference

- `src/batchling/batching/providers/base.py`
- `src/batchling/batching/providers/openai.py`
- `src/batchling/batching/providers/__init__.py`
