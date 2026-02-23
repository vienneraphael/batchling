# Provider adapters

Providers translate between ordinary HTTP requests and provider-specific batch APIs. They
are responsible for URL matching and for reconstructing `httpx.Response` objects from
batch results.

## Responsibilities

- Declare supported hostnames.
- Declare explicit batchable HTTP endpoints (`path`) for hook routing.
- Declare provider-specific terminal batch states used by the core poller.
- Identify whether a URL belongs to a provider.
- Submit provider batches via `process_batch()` (file-based or inline).
- Normalize request URLs for provider batch endpoints.
- Convert JSONL batch result lines into `httpx.Response` objects for callers.

## Registry and lookup

- Providers are auto-discovered from `batchling/providers/*.py` files
  (excluding `__init__.py` and `base.py`).
- `get_provider_for_batch_request()` resolves a provider only when the request's
  `POST + path` is explicitly batchable for that provider.

## OpenAI provider

The OpenAI provider implements:

- `build_api_headers()` for auth + provider-specific passthrough headers.
- file-based batch submission (`/v1/files` then `/v1/batches`).
- `from_batch_result()` to decode batch output lines.

## Gemini provider

The Gemini provider implements:

- dynamic batchable endpoint matching (`/v1beta/models/{model}:generateContent`).
- model extraction from the request endpoint path (for strict queue partitioning).
- file upload via Gemini resumable uploads (`/upload/v1beta/files`).
- model-scoped batch submission path (`/v1beta/models/{model}:batchGenerateContent`).
- poll path override (`/v1beta/batches/{batch_id}`) with `metadata.state` status extraction.
- output file extraction from poll payload (`response.responsesFile`).
- provider-specific result row key mapping (`custom_id_field_name = "key"`).

## Anthropic provider

The Anthropic provider implements:

- inline batch submission to `/v1/messages/batches` (no file upload step).
- provider-specific status polling field (`processing_status`).
- `x-api-key` passthrough via `build_api_headers()`.
- `from_batch_result()` to decode batch output lines.

## Mistral provider

The Mistral provider reuses the file-based flow with provider-specific endpoints:

- `hostnames = ("api.mistral.ai",)`
- `batch_endpoint = "/v1/batch/jobs"`
- `file_upload_endpoint = "/v1/files"`
- `file_content_endpoint = "/v1/files/{id}/content"`

## Together provider

The Together provider follows the same batch lifecycle with provider-specific upload and
batch response shapes:

- `hostnames = ("api.together.xyz",)`
- `batchable_endpoints = ("/v1/chat/completions", "/v1/audio/transcriptions")`
- `file_upload_endpoint = "/v1/files/upload"`
- `file_content_endpoint = "/v1/files/{id}/content"`
- overrides batch file upload form fields (`file_name`, `purpose=batch-api`)
- extracts batch id from nested response payload (`job.id`)

## Xai provider

The Xai provider uses a provider-specific batch lifecycle and response envelope:

- `hostnames = ("api.x.ai",)`
- `batchable_endpoints = ("/v1/chat/completions",)`
- batch container creation at `/v1/batches`, followed by request ingestion at
  `/v1/batches/{batch_id}/requests`
- poll status derived from nested state counters (`state.num_pending`,
  `state.num_completed`) and normalized to `pending` / `running` / `ended`
- result retrieval from `/v1/batches/{batch_id}/results`
- provider-specific result row key (`custom_id_field_name = "batch_request_id"`)

## Doubleword provider

The Doubleword provider reuses the OpenAI provider implementation and only changes:

- `hostnames = ("api.doubleword.ai",)`
- `batchable_endpoints = ("/v1/chat/completions", "/v1/responses", "/v1/embeddings", "/v1/moderations", "/v1/completions")`

Terminal states are inherited unchanged from the OpenAI provider.

Common helpers now live on `BaseProvider` and can be reused by all providers:

- `matches_url()`
- `is_batchable_request()`
- `matches_batchable_endpoint()`
- `normalize_url()`
- `extract_base_and_endpoint()`
- `extract_model_name()`
- `build_jsonl_lines()`
- `build_batch_submit_path()`
- `build_batch_poll_path()`
- `build_batch_results_path()`
- `extract_batch_status()`
- `get_output_file_id_from_poll_response()`
- `encode_body()`

Provider configuration on `BaseProvider` includes:

- `hostnames`
- `batch_method`
- `batchable_endpoints`
- `is_file_based` (switch between file upload flow and inline flow)
- `file_upload_endpoint` (where JSONL input files are uploaded)
- `file_content_endpoint` (where output/error file content is fetched)
- `batch_endpoint` (where the batch job is created)
- `batch_terminal_states` (statuses that stop polling and trigger result resolution)
- `batch_status_field_name` (status field read from poll responses)
- `custom_id_field_name` (result key used to map output rows back to requests)
- `output_file_field_name` / `error_file_field_name`

## Extension notes

- Add new provider classes by subclassing `BaseProvider` in a new module under
  `src/batchling/providers/`.
- Override provider methods as needed (`build_jsonl_lines()`,
  `build_file_based_batch_payload()`, `build_inline_batch_payload()`,
  `build_api_headers()`, `from_batch_result()`).
- Add optional provider-page notes in `docs/providers/_notes/{provider_slug}.md`;
  the docs generator injects them right after the provider endpoint list.
- Define `batch_terminal_states` for the provider so `Batcher` can stop polling at the
  correct lifecycle states.
- Keep `matches_url()` conservative if you override it.

## Code reference

- `src/batchling/providers/base.py`
- `src/batchling/providers/openai.py`
- `src/batchling/providers/xai.py`
- `src/batchling/providers/__init__.py`
