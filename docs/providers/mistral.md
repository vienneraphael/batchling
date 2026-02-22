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

Here's an example showing how to use `batchling` with Mistral:

```python
--8<-- "examples/providers/mistral_example.py"
```
