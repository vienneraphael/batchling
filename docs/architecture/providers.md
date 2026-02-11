# Provider adapters

Providers translate between ordinary HTTP requests and provider-specific batch APIs. They
are responsible for URL matching and for reconstructing `httpx.Response` objects from
batch results.

## Responsibilities

- Declare supported hostnames.
- Declare explicit batchable HTTP endpoints (`path`) for hook routing.
- Identify whether a URL belongs to a provider.
- Submit provider batches via `process_batch()` (upload/create job as needed).
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
- `from_batch_result()` to decode batch output lines.

Common helpers now live on `BaseProvider` and can be reused by all providers:

- `matches_url()`
- `is_batchable_request()`
- `normalize_url()`
- `extract_base_and_endpoint()`
- `build_jsonl_lines()`
- `encode_body()`

## Extension notes

- Add new provider classes by subclassing `BaseProvider` in a new module under
  `src/batchling/batching/providers/`.
- Implement `process_batch()`, `build_api_headers()`, and `from_batch_result()`.
- Keep `matches_url()` conservative if you override it.

## Code reference

- `src/batchling/batching/providers/base.py`
- `src/batchling/batching/providers/openai.py`
- `src/batchling/batching/providers/__init__.py`
