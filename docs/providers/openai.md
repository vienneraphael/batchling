# OpenAI

`batchling` is compatible with OpenAI through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by OpenAI:

- `/v1/responses`
- `/v1/chat/completions`
- `/v1/embeddings`
- `/v1/completions`
- `/v1/moderations`
- `/v1/images/generations`
- `/v1/images/edits`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for OpenAI can be found on the following URL:
--8<-- "docs/providers/_urls/openai.md"

## Example Usage

!!! note "API key required"
    Set `OPENAI_API_KEY` in `.env` or ensure it is already loaded in your environment variables before running batches.

Here's an example showing how to use `batchling` with OpenAI:

```py title="openai_example.py"
--8<-- "examples/providers/openai_example.py"
```

Output:

--8<-- "docs/providers/_outputs/openai.md"
