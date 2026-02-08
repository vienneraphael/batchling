# HTTP hooks: request interception

Hooks intercept HTTP client requests and decide whether to batch them. The current
implementation targets `httpx.AsyncClient.request`, but the hook mechanism is intended to
expand to other clients.

## Responsibilities

- Patch supported HTTP client methods once globally (idempotent install).
- Capture request details for logging and diagnostics.
- Look up the active `Batcher` context and route supported URLs into batching.
- Fall back to the original client behavior for unsupported URLs or when no active
  batcher is set.

## Flow summary

1. `install_hooks()` stores the original method and patches `httpx.AsyncClient.request`.
2. `_httpx_hook()` logs request details and checks `active_batcher`.
3. If a provider supports the URL and a batcher is active, the request is enqueued via
   `batcher.submit()` and an `httpx.Response` is returned later.
4. Otherwise, the original request is invoked.

## Extension notes

- When adding new HTTP client support, mirror the `httpx` pattern: store the original
  method, patch it, and route to `batcher.submit()` when eligible.

## Context vs provider integration tradeoff

Batch routing currently relies on `active_batcher` (a context variable) as an opt-in gate.
There are two main strategies to keep batching behavior correct and ergonomic:

- Context manager scoping (`with` / `async with` on the proxy): reliably sets the active
  batcher for the entire block so any tasks spawned inside inherit it. This is simple,
  predictable, and keeps batching opt-in, but it requires callers to adopt the context
  manager pattern.
- Provider/framework-specific integration: attach the batcher directly to a provider's
  client (or intercept a framework-specific call path) so routing does not rely on task
  context propagation. This is seamless for callers but requires deeper per-provider
  maintenance and is more fragile to upstream SDK changes.

In practice, the context manager is the most stable default, and provider-specific
integration can be added selectively where ergonomics matter most.
