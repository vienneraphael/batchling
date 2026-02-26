# Mistral

`batchling` is compatible with Mistral through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Mistral:

- `/v1/chat/completions`
- `/v1/fim/completions`
- `/v1/embeddings`
- `/v1/moderations`
- `/v1/chat/moderations/v1/ocr`
- `/v1/classifications`
- `/v1/conversations/v1/audio/transcriptions`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for Mistral can be found on the following URL:
--8<-- "docs/providers/_urls/mistral.md"

## Example Usage

!!! note "API key required"
    Set `MISTRAL_API_KEY` in `.env` or ensure it is already loaded in your environment variables before running batches.

Here's an example showing how to use `batchling` with Mistral:

```py title="mistral_example.py"
--8<-- "examples/providers/mistral_example.py"
```

Output:

--8<-- "docs/providers/_outputs/mistral.md"
