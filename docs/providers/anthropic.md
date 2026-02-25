# Anthropic

`batchling` is compatible with Anthropic through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Anthropic:

- `/v1/messages`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

## Example Usage

!!! note "API key required"
    Set `ANTHROPIC_API_KEY` in `.env` or ensure it is already loaded in your environment variables before running batches.

Here's an example showing how to use `batchling` with Anthropic:

```python
--8<-- "examples/providers/anthropic_example.py"
```

Output:

--8<-- "docs/providers/_outputs/anthropic.md"
