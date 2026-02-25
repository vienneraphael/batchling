# Groq

`batchling` is compatible with Groq through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Groq:

- `/openai/v1/chat/completions`
- `/openai/v1/audio/transcriptions`
- `/openai/v1/audio/translations`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for Groq can be found on the following URL:
--8<-- "docs/providers/_urls/groq.md"

## Example Usage

!!! note "API key required"
    Set `GROQ_API_KEY` in `.env` or ensure it is already loaded in your environment variables before running batches.

Here's an example showing how to use `batchling` with Groq:

```python
--8<-- "examples/providers/groq_example.py"
```

Output:

--8<-- "docs/providers/_outputs/groq.md"
