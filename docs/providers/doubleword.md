# Doubleword

`batchling` is compatible with Doubleword through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Doubleword:

- `/v1/chat/completions`
- `/v1/responses`
- `/v1/embeddings`
- `/v1/moderations`
- `/v1/completions`

Here's an example showing how to use `batchling` with Doubleword:

```python
--8<-- "examples/providers/doubleword_example.py"
```
