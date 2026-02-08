# Provider adapters

Providers translate between ordinary HTTP requests and provider-specific batch APIs. They
are responsible for URL matching and for reconstructing `httpx.Response` objects from
batch results.

## Responsibilities

- Declare supported hostnames and path prefixes.
- Identify whether a URL belongs to a provider.
- Normalize request URLs if required by the provider's batch API.
- Convert JSONL batch result lines into `httpx.Response` objects for callers.

## Registry and lookup

- Providers are registered in `batchling.batching.providers`.
- `get_provider_for_url()` indexes providers by hostname and path prefix for efficient
  lookup, with a fallback match if indices do not produce a candidate.

## OpenAI provider

The OpenAI provider implements `from_batch_result()` to:

- Extract success or error payloads from a batch result line.
- Convert payloads into raw bytes.
- Return an `httpx.Response` with appropriate headers.

## Extension notes

- Add new provider classes by subclassing `BaseProvider` and registering them in
  `PROVIDERS`.
- Keep `matches_url()` conservative to avoid batch-routing unsupported URLs.
