# Batchling batching architecture

This document provides a top-level map of the batching subsystem in `src/batchling/batching` and links to
component-level references.

## Component index

- [API surface: `batchify` adapter](architecture/api.md)
- [Batching engine: `Batcher` lifecycle](architecture/core.md)
- [HTTP hooks: request interception](architecture/hooks.md)
- [Proxy wrapper: `BatchingProxy`](architecture/proxy.md)
- [Provider adapters: URL matching + response decoding](architecture/providers.md)

## End-to-end flow (high level)

1. Callers wrap a function or client instance with `batchify`, which creates a `Batcher` and installs hooks.
2. `BatchingProxy` (or the function wrapper) activates a context variable holding the `Batcher`.
3. HTTP hooks intercept supported requests and enqueue them into the `Batcher`.
4. The `Batcher` batches pending requests, submits them, and resolves per-request futures.
5. Provider adapters normalize URLs and decode batch API results back into HTTP responses.

See the component pages above for detailed behavior and extension points.
