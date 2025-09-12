from typer.testing import CliRunner

from batchling.cli.main import app

runner = CliRunner()


def test_create_experiment():
    result = runner.invoke(
        app,
        [
            "create",
            "--id",
            "test-cli-1",
            "--model",
            "gpt-4o-mini",
            "--title",
            "test cli 1",
            "--description",
            "test cli experiment number 1",
            "--provider",
            "openai",
            "--endpoint",
            "/v1/chat/completions",
            "--raw-file-path",
            "tests/test_data/raw_file_countries.jsonl",
            "--processed-file-path",
            "input_capitals.jsonl",
            "--results-file-path",
            "output/result_capitals.jsonl",
        ],
    )
    assert result.exit_code == 0


def test_delete_experiment():
    result = runner.invoke(app, ["delete", "test-cli-1"])
    assert result.exit_code == 0
    assert "deleted" in result.output
