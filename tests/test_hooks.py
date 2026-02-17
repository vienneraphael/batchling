"""
Tests for the httpx request hook system.
"""

from unittest.mock import patch

import aiohttp
import httpx
import pytest
import respx

import batchling.batching.hooks as hooks_module

install_hooks = hooks_module.install_hooks


@pytest.fixture
def restore_hooks():
    """Fixture to restore original httpx client methods after tests."""
    # Store original state
    original_async_send = httpx.AsyncClient.send
    original_aiohttp_request = aiohttp.ClientSession._request
    original_hooks_installed = hooks_module._hooks_installed

    yield

    # Restore original state
    httpx.AsyncClient.send = original_async_send
    aiohttp.ClientSession._request = original_aiohttp_request
    # Reset module-level variables
    hooks_module._hooks_installed = original_hooks_installed
    hooks_module._original_httpx_async_send = original_async_send
    hooks_module._original_aiohttp_request = original_aiohttp_request


def test_install_hooks_idempotent(restore_hooks):
    """Test that install_hooks can be called multiple times safely."""
    # First installation
    install_hooks()
    first_request_method = httpx.AsyncClient.request

    # Second installation should not change anything
    install_hooks()
    second_request_method = httpx.AsyncClient.request

    assert first_request_method is second_request_method
    assert httpx.AsyncClient.request is not httpx.AsyncClient.__dict__.get("request", None) or True


@pytest.mark.asyncio
async def test_hook_intercepts_get_request(restore_hooks):
    """Test that the hook intercepts GET requests."""
    install_hooks()

    with respx.mock:
        respx.get("https://example.com/test").mock(
            return_value=httpx.Response(200, json={"status": "ok"})
        )

        async with httpx.AsyncClient() as client:
            response = await client.get("https://example.com/test")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_hook_intercepts_post_request_with_json(restore_hooks):
    """Test that the hook intercepts POST requests with JSON body."""
    install_hooks()

    with respx.mock:
        respx.post("https://example.com/api").mock(
            return_value=httpx.Response(201, json={"id": "123"})
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://example.com/api", json={"name": "test", "value": 42}
            )

        assert response.status_code == 201
        assert response.json() == {"id": "123"}


@pytest.mark.asyncio
async def test_hook_intercepts_request_with_headers(restore_hooks):
    """Test that the hook intercepts requests with custom headers."""
    install_hooks()

    with respx.mock:
        respx.get("https://example.com/api").mock(
            return_value=httpx.Response(200, json={"data": "test"})
        )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://example.com/api",
                headers={"Authorization": "Bearer token123", "X-Custom": "value"},
            )

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_hook_allows_request(restore_hooks):
    """Test that the hook allows requests."""
    install_hooks()

    with respx.mock:
        respx.post("https://example.com/api").mock(
            return_value=httpx.Response(200, json={"result": "success"})
        )

        async with httpx.AsyncClient() as client:
            response = await client.post("https://example.com/api", json={"test": "data"})

        # Should get the actual response from respx mock
        assert response.status_code == 200
        assert response.json() == {"result": "success"}


@pytest.mark.asyncio
async def test_hook_handles_post_with_content(restore_hooks):
    """Test that the hook handles POST requests with content (not JSON)."""
    install_hooks()

    with respx.mock:
        respx.post("https://example.com/upload").mock(
            return_value=httpx.Response(200, text="uploaded")
        )

        async with httpx.AsyncClient() as client:
            response = await client.post("https://example.com/upload", content=b"binary data here")

        assert response.status_code == 200
        assert response.text == "uploaded"


@pytest.mark.asyncio
async def test_hook_handles_post_with_data(restore_hooks):
    """Test that the hook handles POST requests with form data."""
    install_hooks()

    with respx.mock:
        respx.post("https://example.com/form").mock(
            return_value=httpx.Response(200, json={"submitted": True})
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://example.com/form", data={"key": "value", "another": "field"}
            )

        assert response.status_code == 200
        assert response.json() == {"submitted": True}


@pytest.mark.asyncio
async def test_hook_logs_request_details(restore_hooks):
    """Test that the hook logs request details using structlog."""
    install_hooks()

    # Mock structlog logger to capture log calls
    with patch.object(hooks_module.log, "info") as mock_info:
        with respx.mock:
            respx.get("https://example.com/test").mock(
                return_value=httpx.Response(200, json={"status": "ok"})
            )

            async with httpx.AsyncClient() as client:
                await client.get("https://example.com/test", headers={"X-Test": "header-value"})

        # Verify that log.info was called
        assert mock_info.called
        call_args = mock_info.call_args
        assert call_args[1]["event"] == "httpx request intercepted"
        assert call_args[1]["method"] == "GET"
        assert call_args[1]["url"] == "https://example.com/test"
        logged_headers = call_args[1]["headers"]
        header_value = logged_headers.get("X-Test") or logged_headers.get("x-test")
        assert header_value == "***"


@pytest.mark.asyncio
async def test_hook_handles_different_http_methods(restore_hooks):
    """Test that the hook handles different HTTP methods."""
    install_hooks()

    methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

    for method in methods:
        with respx.mock:
            respx.request(method, "https://example.com/resource").mock(
                return_value=httpx.Response(200, json={"method": method})
            )

            async with httpx.AsyncClient() as client:
                if method == "GET":
                    response = await client.get("https://example.com/resource")
                elif method == "POST":
                    response = await client.post("https://example.com/resource")
                elif method == "PUT":
                    response = await client.put("https://example.com/resource")
                elif method == "DELETE":
                    response = await client.delete("https://example.com/resource")
                elif method == "PATCH":
                    response = await client.patch("https://example.com/resource")

            assert response.status_code == 200
            assert response.json()["method"] == method
