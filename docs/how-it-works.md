# How it works

This documentation section aims to give a high-level explanation of what happens under the hood when you run `batchling` through the [SDK](./python-sdk.md) or [CLI](./cli.md).

There are basically three components working together hand in hand, in order:

1. The context manager

2. The HTTP hooks

3. The batcher

Let's detail the role of each of them next.

## Context manager

This is the `batchify` function you call in the SDK (or that is called for you if you use the CLI).

What it does:

- Install HTTP hooks to capture target incoming HTTP requests

- Initialize the batcher, which will do most of the hard work later

- Activate a `BatchingContext` context var when the user enters the context, basically saying "batch mode is activated" at the context manager scope

## HTTP Hooks

The HTTP hooks are installed by the context manager.

Essentially, they patch the `httpx` and `aiohttp` libraries such that incoming requests matching certain characteristics (hostname, endpoint, method..) are captured.

The requests that are not captured just flow naturally like if nothing happened, which makes `batchling` **non-intrusive**.

The captured requests are repurposed and sent to the batcher for further processing.

## Batcher

The batcher receives tons of requests coming from differents sources.

His role is the one of the orchestrator:

- Sorts requests by the provider, endpoint, model triplet. This is required because most Batch APIs don't allow mixing models and endpoints.

- In practice, the batcher manages a set of queues that represent future batches (stack of requests).

- Monitors time elapsed since a request spawned a queue and each queue size.

- Uses the providers abstraction to submit, poll and download results from batches.

- Returns results as a dump of HTTP Responses, like if nothing had happened in the middle.

Finally, the batcher sends back those responses to the patched HTTP client, which returns them to your framework of choice, and the code continues its execution.
