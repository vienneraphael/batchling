# Doubleword

`batchling` is compatible with Doubleword through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Doubleword:

- `/v1/chat/completions`
- `/v1/responses`
- `/v1/embeddings`
- `/v1/moderations`
- `/v1/completions`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for Doubleword can be found on the following URL:
--8<-- "docs/providers/_urls/doubleword.md"

## Example Usage

!!! note "API key required"
    Set `DOUBLEWORD_API_KEY` in `.env` or ensure it is already loaded in your environment variables before running batches.

Here's an example showing how to use `batchling` with Doubleword:

```py title="doubleword_example.py"
--8<-- "examples/providers/doubleword_example.py"
```

Output:

--8<-- "docs/providers/_outputs/doubleword.md"
