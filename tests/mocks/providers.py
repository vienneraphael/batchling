import re

import httpx


def setup_openai_mocks(respx_mock):
    openai_base = "https://api.openai.com/v1"
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
                "metadata": {"state": "BATCH_STATE_SUCCEEDED"},
                "response": {"responsesFile": "files/results-123"},
            },
        )
    )
    respx_mock.get(
        f"{gemini_download_base}/files/results-123:download", params={"alt": "media"}
    ).mock(return_value=httpx.Response(200, text='{"response": {"candidates": []}}\n'))
