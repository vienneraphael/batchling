import re

import httpx


def setup_openai_mocks(respx_mock):
    openai_base = "https://api.openai.com/v1"
    # Output file content (JSONL text)
    respx_mock.get(re.compile(r"https://api\.openai\.com/v1/files/.+/content")).mock(
        return_value=httpx.Response(
            200,
            text=(
                '{"id": "batch_req_68f9b269e46c8190af88ba8f4f5cc4d1", "custom_id": "openai-sample-0", "response": {"status_code": 200, "request_id": "26ce92a1278fdfb9d35c3e65a116d051", "body": {"id": "chatcmpl-CThRK5DtRl6Xgw8vRJORopZt9v3vD", "object": "chat.completion", "created": 1761194530, "model": "gpt-4o-2024-08-06", "choices": [{"index": 0, "message": {"role": "assistant", "content": "The capital of France is Paris.", "refusal": null, "annotations": []}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 24, "completion_tokens": 7, "total_tokens": 31, "prompt_tokens_details": {"cached_tokens": 0, "audio_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 0, "audio_tokens": 0, "accepted_prediction_tokens": 0, "rejected_prediction_tokens": 0}}, "service_tier": "default", "system_fingerprint": "fp_cbf1785567"}}, "error": null}\n'
                '{"id": "batch_req_68f9b269f8048190ab59dbcf468b68e1", "custom_id": "openai-sample-1", "response": {"status_code": 200, "request_id": "7d868feef646aa862954c6de97cd8dab", "body": {"id": "chatcmpl-CThSIAEtAErWx7xN833S2ASWiy5xP", "object": "chat.completion", "created": 1761194590, "model": "gpt-4o-2024-08-06", "choices": [{"index": 0, "message": {"role": "assistant", "content": "The capital of Italy is Rome.", "refusal": null, "annotations": []}, "finish_reason": "stop"}], "usage": {"prompt_tokens": 24, "completion_tokens": 7, "total_tokens": 31, "prompt_tokens_details": {"cached_tokens": 0, "audio_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 0, "audio_tokens": 0, "accepted_prediction_tokens": 0, "rejected_prediction_tokens": 0}}, "service_tier": "default", "system_fingerprint": "fp_cbf1785567"}}, "error": null}\n'
            ),
        )
    )
    respx_mock.post(f"{openai_base}/files").mock(
        return_value=httpx.Response(200, json={"id": "file-123"})
    )
    respx_mock.get(re.compile(r"https://api\.openai\.com/v1/files/.+")).mock(
        return_value=httpx.Response(200, json={"id": "file-123"})
    )
    respx_mock.post(f"{openai_base}/batches").mock(
        return_value=httpx.Response(200, json={"id": "batch-123"})
    )
    respx_mock.get(re.compile(r"https://api\.openai\.com/v1/batches/.+")).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "batch-123",
                "status": "completed",
                "output_file_id": "file-456",
            },
        )
    )


def setup_groq_mocks(respx_mock):
    groq_base = "https://api.groq.com/openai/v1"
    # Output file content (JSONL text)
    respx_mock.get(re.compile(r"https://api\.groq\.com/openai/v1/files/.+/content")).mock(
        return_value=httpx.Response(
            200,
            text=(
                '{"id": "batch_req_groq_1", "custom_id": "groq-sample-0", "response": {"status_code": 200, "body": {"id": "chatcmpl-1", "object": "chat.completion", "model": "llama3-70b", "choices": [{"index": 0, "message": {"role": "assistant", "content": "The capital of France is Paris."}, "finish_reason": "stop"}]}}}\n'
                '{"id": "batch_req_groq_2", "custom_id": "groq-sample-1", "response": {"status_code": 200, "body": {"id": "chatcmpl-2", "object": "chat.completion", "model": "llama3-70b", "choices": [{"index": 0, "message": {"role": "assistant", "content": "The capital of Italy is Rome."}, "finish_reason": "stop"}]}}}\n'
            ),
        )
    )
    respx_mock.post(f"{groq_base}/files").mock(
        return_value=httpx.Response(200, json={"id": "file-123"})
    )
    respx_mock.get(re.compile(r"https://api\.groq\.com/openai/v1/files/.+")).mock(
        return_value=httpx.Response(200, json={"id": "file-123"})
    )
    respx_mock.post(f"{groq_base}/batches").mock(
        return_value=httpx.Response(200, json={"id": "batch-123"})
    )
    respx_mock.get(re.compile(r"https://api\.groq\.com/openai/v1/batches/.+")).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "batch-123",
                "status": "completed",
                "output_file_id": "file-456",
            },
        )
    )


def setup_mistral_mocks(respx_mock):
    mistral_base = "https://api.mistral.ai/v1"
    # Output file content (JSONL text)
    respx_mock.get(re.compile(r"https://api\.mistral\.ai/v1/files/.+/content")).mock(
        return_value=httpx.Response(
            200,
            text=(
                '{"id":"batch-cdb26ba2-1-a8cc8a5c-eb6e-4093-a262-8ed84e706abc","custom_id":"mistral-sample-0","response":{"status_code":200,"body":{"id":"5ea658ebb8bf4574a51cfd132dadd634","object":"chat.completion","model":"mistral-small-latest","usage":{"prompt_tokens":18,"completion_tokens":8,"total_tokens":26},"created":1761194461,"choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":"The capital of France is Paris.","tool_calls":null}}]}} ,"error":null}\n'
                '{"id":"batch-cdb26ba2-2-ede8580c-d792-4c9a-b964-299053cb2cfb","custom_id":"mistral-sample-1","response":{"status_code":200,"body":{"id":"4aef7e0a5c8a4895ac4e68ccaa31dafc","object":"chat.completion","model":"mistral-small-latest","usage":{"prompt_tokens":18,"completion_tokens":8,"total_tokens":26},"created":1761194461,"choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant","content":"The capital of Italy is Rome.","tool_calls":null}}]}} ,"error":null}\n'
            ),
        )
    )
    respx_mock.post(f"{mistral_base}/files").mock(
        return_value=httpx.Response(200, json={"id": "file-123"})
    )
    respx_mock.get(re.compile(r"https://api\.mistral\.ai/v1/files/.+")).mock(
        return_value=httpx.Response(200, json={"id": "file-123"})
    )
    respx_mock.post(f"{mistral_base}/batch/jobs").mock(
        return_value=httpx.Response(200, json={"id": "job-123"})
    )
    respx_mock.get(re.compile(r"https://api\.mistral\.ai/v1/batch/jobs/.+")).mock(
        return_value=httpx.Response(
            200,
            json={"id": "job-123", "status": "SUCCESS", "output_file": "file-456"},
        )
    )


def setup_together_mocks(respx_mock):
    together_base = "https://api.together.xyz/v1"
    # Output file content (JSONL text)
    respx_mock.get(re.compile(r"https://api\.together\.xyz/v1/files/.+/content")).mock(
        return_value=httpx.Response(
            200,
            text=(
                '{"id": "batch_req_together_1", "custom_id": "together-sample-0", "response": {"status_code": 200, "body": {"id": "chatcmpl-1", "object": "chat.completion", "model": "meta-llama/Meta-Llama-3-70B-Instruct-Turbo", "choices": [{"index": 0, "message": {"role": "assistant", "content": "The capital of France is Paris."}, "finish_reason": "stop"}]}}}\n'
                '{"id": "batch_req_together_2", "custom_id": "together-sample-1", "response": {"status_code": 200, "body": {"id": "chatcmpl-2", "object": "chat.completion", "model": "meta-llama/Meta-Llama-3-70B-Instruct-Turbo", "choices": [{"index": 0, "message": {"role": "assistant", "content": "The capital of Italy is Rome."}, "finish_reason": "stop"}]}}}\n'
            ),
        )
    )
    respx_mock.post(f"{together_base}/files/upload").mock(
        return_value=httpx.Response(200, json={"id": "file-123"})
    )
    respx_mock.get(re.compile(r"https://api\.together\.xyz/v1/files/.+")).mock(
        return_value=httpx.Response(200, json={"id": "file-123"})
    )
    respx_mock.post(f"{together_base}/batches").mock(
        return_value=httpx.Response(200, json={"job": {"id": "job-123"}})
    )
    respx_mock.get(re.compile(r"https://api\.together\.xyz/v1/batches/.+")).mock(
        return_value=httpx.Response(
            200,
            json={"id": "job-123", "status": "COMPLETED", "output_file_id": "file-456"},
        )
    )


def setup_anthropic_mocks(respx_mock):
    anthropic_base = "https://api.anthropic.com/v1/messages/batches"
    # Output file content (JSONL text) served from the results URL
    respx_mock.get(re.compile(r"https://anthropic-results\.test/.+")).mock(
        return_value=httpx.Response(
            200,
            text=(
                '{"type":"success","custom_id":"anthropic-sample-0","result":{"message":{"id":"msg_123","model":"claude-3-5-sonnet-20241022","content":[{"type":"text","text":"The capital of France is Paris."}]}}}\n'
                '{"type":"success","custom_id":"anthropic-sample-1","result":{"message":{"id":"msg_456","model":"claude-3-5-sonnet-20241022","content":[{"type":"text","text":"The capital of Italy is Rome."}]}}}\n'
            ),
        )
    )
    respx_mock.post(anthropic_base).mock(
        return_value=httpx.Response(
            200, json={"id": "msgbatch_123", "processing_status": "in_progress"}
        )
    )
    respx_mock.get(re.compile(r"https://api\.anthropic\.com/v1/messages/batches/.+")).mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "msgbatch_123",
                "processing_status": "ended",
                "results_url": "https://anthropic-results.test/msgbatch_123.jsonl",
            },
        )
    )


def setup_gemini_mocks(respx_mock):
    gemini_base = "https://generativelanguage.googleapis.com/v1beta"
    gemini_upload_base = "https://generativelanguage.googleapis.com/upload/v1beta"
    gemini_download_base = "https://generativelanguage.googleapis.com/download/v1beta"

    respx_mock.post(
        f"{gemini_upload_base}/files",
        headers={"X-Goog-Upload-Command": "start"},
    ).mock(
        return_value=httpx.Response(
            200,
            headers={"X-Goog-Upload-URL": f"{gemini_upload_base}/files?upload_id=abc123"},
        )
    )
    respx_mock.post(
        re.compile(
            r"https://generativelanguage\.googleapis\.com/upload/v1beta/files\?upload_id=abc123"
        )
    ).mock(
        return_value=httpx.Response(
            200,
            content=b'{"file": {"name": "files/abc123"}}',
            headers={"Content-Type": "application/json"},
        )
    )
    respx_mock.post(
        f"{gemini_upload_base}/files",
        headers={"X-Goog-Upload-Command": "upload, finalize"},
    ).mock(
        return_value=httpx.Response(
            200,
            content=b'{"file": {"name": "files/abc123"}}',
            headers={"Content-Type": "application/json"},
        )
    )
    respx_mock.post(
        re.compile(r"https://generativelanguage\.googleapis\.com/upload/v1beta/files\?.+")
    ).mock(return_value=httpx.Response(200, json={"file": {"name": "files/abc123"}}))
    respx_mock.get(re.compile(r"https://generativelanguage\.googleapis\.com/v1beta/files/.+")).mock(
        return_value=httpx.Response(200, json={"name": "files/abc123"})
    )
    respx_mock.post(
        re.compile(
            r"https://generativelanguage\.googleapis\.com/v1beta/models/.+:batchGenerateContent"
        )
    ).mock(return_value=httpx.Response(200, json={"name": "batches/123"}))
    respx_mock.get(f"{gemini_base}/batches/123").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "batches/123",
                "metadata": {"state": "BATCH_STATE_SUCCEEDED"},
                "response": {"responsesFile": "files/results-123"},
            },
        )
    )
    respx_mock.get(
        f"{gemini_download_base}/files/results-123:download", params={"alt": "media"}
    ).mock(
        return_value=httpx.Response(
            200,
            text=(
                '{"response":{"usageMetadata":{"candidatesTokenCount":8,"promptTokensDetails":[{"modality":"TEXT","tokenCount":13}],"promptTokenCount":13,"totalTokenCount":21,"candidatesTokensDetails":[{"tokenCount":8,"modality":"TEXT"}]},"modelVersion":"gemini-2.0-flash","candidates":[{"content":{"parts":[{"text":"The capital of France is Paris."}],"role":"model"},"finishReason":"STOP"}],"responseId":"JbL5aKK8Bdzgz7IPu7C48AY"},"key":"gemini-sample-0"}\n'
                '{"key":"gemini-sample-1","response":{"modelVersion":"gemini-2.0-flash","usageMetadata":{"promptTokenCount":13,"candidatesTokenCount":8,"totalTokenCount":21,"promptTokensDetails":[{"tokenCount":13,"modality":"TEXT"}],"candidatesTokensDetails":[{"modality":"TEXT","tokenCount":8}]},"candidates":[{"content":{"parts":[{"text":"The capital of Italy is Rome."}],"role":"model"},"finishReason":"STOP"}],"responseId":"JbL5aMvPAqCsz7IPsKH2qQs"}}\n'
            ),
        )
    )
