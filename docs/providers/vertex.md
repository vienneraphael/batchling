# Vertex

`batchling` is compatible with Vertex through any [supported framework](../frameworks.md){ data-preview }

The following endpoints are made batch-compatible by Vertex:

- `/v1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent`
- `/v1beta1/projects/{project}/locations/{location}/publishers/google/models/{model}:generateContent`

!!! warning "Check model support and batch pricing"
    Before sending batches, review the provider's official pricing page for supported models and batch pricing details.

The Batch API docs for Vertex can be found on the following URL:
--8<-- "docs/providers/_urls/vertex.md"

## Example Usage

--8<-- "docs/providers/_credentials/vertex.md"

Here's an example showing how to use `batchling` with Vertex:

```py title="vertex_example.py"
--8<-- "examples/providers/vertex_example.py"
```
