# XAI

`batchling` is compatible with XAI through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by XAI:

- `/v1/chat/completions`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for XAI can be found on the following URL:
--8<-- "docs/providers/_urls/xai.md"

--8<-- "docs/providers/_notes/xai.md"

## Example Usage

!!! note "API key required"
    Set `XAI_API_KEY` in `.env` or ensure it is already loaded in your environment variables before running batches.

Here's an example showing how to use `batchling` with XAI:

```py title="xai_example.py"
--8<-- "examples/providers/xai_example.py"
```

Output:

--8<-- "docs/providers/_outputs/xai.md"
