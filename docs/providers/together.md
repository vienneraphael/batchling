# Together

`batchling` is compatible with Together through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Together:

- `/v1/chat/completions`
- `/v1/audio/transcriptions`

Here's an example showing how to use `batchling` with Together:

```python
--8<-- "examples/providers/together_example.py"
```
