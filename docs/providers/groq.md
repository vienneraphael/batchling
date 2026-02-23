# Groq

`batchling` is compatible with Groq through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Groq:

- `/openai/v1/chat/completions`
- `/openai/v1/audio/transcriptions`
- `/openai/v1/audio/translations`

## Example Usage

Here's an example showing how to use `batchling` with Groq:

```python
--8<-- "examples/providers/groq_example.py"
```
