# Providers

batchling currently supports these provider adapters.

| Provider | Batch docs |
| --- | --- |
| OpenAI | <https://platform.openai.com/docs/guides/batch> |
| Anthropic | <https://docs.anthropic.com/en/docs/build-with-claude/batch-processing> |
| Gemini | <https://ai.google.dev/gemini-api/docs/batch-mode> |
| Groq | <https://console.groq.com/docs/batch> |
| Mistral | <https://docs.mistral.ai/capabilities/batch/> |
| Together AI | <https://docs.together.ai/docs/batch-inference> |
| Doubleword | <https://docs.doubleword.ai/batches/getting-started-with-batched-api> |

## Compatibility notes

- Matching is based on provider hostname plus supported batchable endpoints.
- Requests that are not recognized as batchable are not routed through the batch engine.
- Provider response decoding is normalized back into request-level responses.

Implementation details for adapters are kept in AGENTS-oriented internal docs.
