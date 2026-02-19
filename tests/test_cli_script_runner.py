import json
from pathlib import Path

import httpx
from typer.testing import CliRunner

import batchling.cli.main as cli_main
from batchling import DeferredExit
from batchling.cli.main import app

runner = CliRunner()


class DummyAsyncBatchifyContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_run_script_function_with_positional_and_keyword_args(tmp_path: Path, monkeypatch):
    script_path = tmp_path / "script.py"
    script_path.write_text(
        "\n".join(
            [
                "import json",
                "async def foo(*args, **kwargs):",
                "    print(json.dumps({'args': list(args), 'kwargs': kwargs}))",
            ]
        )
        + "\n"
    )
    captured_batchify_kwargs: dict = {}

    def fake_batchify(**kwargs):
        captured_batchify_kwargs.update(kwargs)
        return DummyAsyncBatchifyContext()

    monkeypatch.setattr(cli_main, "batchify", fake_batchify)

    result = runner.invoke(
        app,
        [
            f"{script_path.as_posix()}:foo",
            "a",
            "b",
            "--name",
            "alice",
            "--count=3",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output.strip().splitlines()[-1])
    assert payload == {
        "args": ["a", "b"],
        "kwargs": {
            "name": "alice",
            "count": "3",
        },
    }
    assert captured_batchify_kwargs["dry_run"] is True
    assert captured_batchify_kwargs["cache"] is True
    assert captured_batchify_kwargs["deferred"] is False
    assert captured_batchify_kwargs["deferred_idle_seconds"] == 60.0


def test_run_script_with_cache_and_deferred_options(tmp_path: Path, monkeypatch):
    script_path = tmp_path / "script.py"
    script_path.write_text(
        "\n".join(
            [
                "async def foo(*args, **kwargs):",
                "    return None",
            ]
        )
        + "\n"
    )
    captured_batchify_kwargs: dict = {}

    def fake_batchify(**kwargs):
        captured_batchify_kwargs.update(kwargs)
        return DummyAsyncBatchifyContext()

    monkeypatch.setattr(cli_main, "batchify", fake_batchify)

    result = runner.invoke(
        app,
        [
            f"{script_path.as_posix()}:foo",
            "--no-cache",
            "--deferred",
            "--deferred-idle-seconds",
            "15",
        ],
    )

    assert result.exit_code == 0
    assert captured_batchify_kwargs["cache"] is False
    assert captured_batchify_kwargs["deferred"] is True
    assert captured_batchify_kwargs["deferred_idle_seconds"] == 15.0


def test_script_path_requires_module_function_syntax(tmp_path: Path):
    script_path = tmp_path / "script.py"
    script_path.write_text("async def foo():\n    return None\n")

    result = runner.invoke(app, [script_path.as_posix()])

    assert result.exit_code == 2
    assert "module:func" in result.output


def test_run_script_invalid_script_path():
    result = runner.invoke(app, ["does-not-exist.py:foo"])

    assert result.exit_code == 1
    assert "Script not found" in result.output


def test_cli_catches_deferred_exit(tmp_path: Path, monkeypatch):
    script_path = tmp_path / "script.py"
    script_path.write_text("async def foo():\n    return None\n")

    async def failing_run_script_with_batchify(**kwargs):
        del kwargs
        raise DeferredExit("deferred")

    monkeypatch.setattr(
        cli_main,
        "run_script_with_batchify",
        failing_run_script_with_batchify,
    )

    result = runner.invoke(
        app,
        [f"{script_path.as_posix()}:foo", "--deferred"],
    )

    assert result.exit_code == 0
    assert "Deferred mode: batches are underway" in result.output


def test_cli_catches_deferred_wrapped_error(tmp_path: Path, monkeypatch):
    script_path = tmp_path / "script.py"
    script_path.write_text("async def foo():\n    return None\n")

    async def failing_run_script_with_batchify(**kwargs):
        del kwargs
        deferred_response = httpx.Response(
            status_code=499,
            headers={"x-batchling-deferred": "1"},
            json={"error": {"type": "deferred_exit"}},
        )
        raise RuntimeError("wrapped") from httpx.HTTPStatusError(
            message="deferred",
            request=httpx.Request(method="POST", url="https://api.anthropic.com/v1/messages"),
            response=deferred_response,
        )

    monkeypatch.setattr(
        cli_main,
        "run_script_with_batchify",
        failing_run_script_with_batchify,
    )

    result = runner.invoke(
        app,
        [f"{script_path.as_posix()}:foo", "--deferred"],
    )

    assert result.exit_code == 0
    assert "Deferred mode: batches are underway" in result.output
