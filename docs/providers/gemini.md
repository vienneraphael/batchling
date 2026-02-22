# Gemini

`batchling` is compatible with Gemini through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Gemini:

- `/v1beta/models/{model}:generateContent`

Here's an example showing how to use `batchling` with Gemini:

```python
--8<-- "examples/providers/gemini_example.py"
```
