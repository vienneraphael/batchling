import json
from pathlib import Path

from typer.testing import CliRunner

import batchling.cli.main as cli_main
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
