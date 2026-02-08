# Batch-native OpenAI client: `BatchOpenAI`

`BatchOpenAI` is a specialized client that mirrors the `AsyncOpenAI` interface while
submitting requests directly to the provider batch API. It is separate from the generic
hooking approach and implements its own queueing, submission, and polling loop.

## Responsibilities

- Mirror `AsyncOpenAI` surface for chat completions via a `chat.completions.create` proxy.
- Collect pending requests and submit them as JSONL batch files.
- Poll active batches and resolve per-request futures.
- Stream partial results via output file offsets when available.

## Flow summary

1. `_enqueue_request()` queues a request and starts the batch window timer.
2. `_submit_batch()` uploads a JSONL file, creates a batch, and starts the poller.
3. `_poll_batches()` checks batch status and fetches partial or completed results.
4. `_fetch_partial_results()` streams incremental results to waiting futures.
5. `close()` shuts down timers and HTTP resources.

## Extension notes

- The implementation currently focuses on chat completions; extend the proxy pattern
  to other endpoints if needed.
- Consider reusing provider adapters once batch submission is unified across the
  generic `Batcher` and the specialized client.
