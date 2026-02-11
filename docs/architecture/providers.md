# Provider adapters

Providers translate between ordinary HTTP requests and provider-specific batch APIs. They
are responsible for URL matching and for reconstructing `httpx.Response` objects from
batch results.

## Responsibilities

- Declare supported hostnames and path prefixes.
- Identify whether a URL belongs to a provider.
- Submit provider batches via `process_batch()` (upload/create job as needed).
- Normalize request URLs for provider batch endpoints.
- Convert JSONL batch result lines into `httpx.Response` objects for callers.

## Registry and lookup

- Providers are registered in `batchling.batching.providers`.
- `get_provider_for_url()` indexes providers by hostname and path prefix for efficient
  lookup, with a fallback match if indices do not produce a candidate.

## OpenAI provider

The OpenAI provider implements:

- `build_api_headers()` for auth + provider-specific passthrough headers.
- `process_batch()` to upload JSONL input and create `/v1/batches` jobs.
- `from_batch_result()` to decode batch output lines.

Common helpers now live on `BaseProvider` and can be reused by all providers:

- `matches_url()`
- `normalize_url()`
- `extract_base_and_endpoint()`
- `build_jsonl_lines()`
- `encode_body()`

## Extension notes

- Add new provider classes by subclassing `BaseProvider` and registering them in
  `PROVIDERS`.
- Implement `process_batch()`, `build_api_headers()`, and `from_batch_result()`.
- Keep `matches_url()` conservative if you override it.

## Code reference

- `src/batchling/batching/providers/base.py`
- `src/batchling/batching/providers/openai.py`
- `src/batchling/batching/providers/__init__.py`
