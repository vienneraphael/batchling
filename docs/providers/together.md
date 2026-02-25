# Together

`batchling` is compatible with Together through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Together:

- `/v1/chat/completions`
- `/v1/audio/transcriptions`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for Together can be found on the following URL:
--8<-- "docs/providers/_urls/together.md"

## Example Usage

!!! note "API key required"
    Set `TOGETHER_API_KEY` in `.env` or ensure it is already loaded in your environment variables before running batches.

Here's an example showing how to use `batchling` with Together:

```python
--8<-- "examples/providers/together_example.py"
```

Output:

--8<-- "docs/providers/_outputs/together.md"
