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

Here's an example showing how to use `batchling` with OpenAI:

```python
--8<-- "examples/providers/openai_example.py"
```
