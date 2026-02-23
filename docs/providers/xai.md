# XAI

`batchling` is compatible with XAI through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by XAI:

- `/v1/chat/completions`

--8<-- "docs/providers/_notes/xai.md"

Here's an example showing how to use `batchling` with XAI:

```python
--8<-- "examples/providers/xai_example.py"
```
