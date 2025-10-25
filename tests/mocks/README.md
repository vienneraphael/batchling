# Provider HTTP mocks (respx)

Overview
This folder contains reusable respx-based HTTP mocks for provider APIs used by tests. Mocks are realistic and mirror current API contracts just enough for unit tests to run without network access.

Files

- providers.py: per-provider setup helpers that register respx routes.

How it integrates

- tests/conftest.py imports the helpers and exposes an autouse dispatcher fixture that:
  - Installs only the relevant provider’s mocks when a test uses the `provider` fixture.
  - Falls back to installing all provider mocks when no provider is parameterized.

Add a new provider

1) Create a `setup_<provider>_mocks(respx_mock)` function in providers.py.
2) Register required routes used by your Experiment implementation (file upload, batch create, batch status/results, etc.).
3) Add the setup function to `provider_setups` in tests/conftest.py.

Override mocks in a specific test
You can extend/override routes in a test by using the `respx_mock` fixture directly:

```python
def test_custom_case(respx_mock):
    respx_mock.get("https://api.openai.com/v1/batches/batch-override").mock(
        return_value=httpx.Response(200, json={"id": "batch-override", "status": "completed"})
    )
    # run assertions
```

Environment variables
Tests rely on API keys being present. `tests/conftest.py` sets them via an autouse env fixture to avoid ValueError from `get_default_api_key_from_provider`.

Notes on Gemini resumable uploads
Gemini mocks account for resumable upload semantics by matching `X-Goog-Upload-Command` headers and finalize URLs with `upload_id`. If you change upload logic, update the gemini setup accordingly.

Negative paths
If you need error-path coverage, add additional routes returning 4xx/5xx and write tests asserting correct error handling.
