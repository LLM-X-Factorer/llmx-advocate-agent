from click.testing import CliRunner

from llmx_advocate.cli.main import cli


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "task" in result.output
    assert "eval" in result.output


def test_task_subcommand_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["task", "--help"])
    assert result.exit_code == 0
    assert "new" in result.output
    assert "fork" in result.output


def test_task_new_reports_api_unreachable(tmp_path, monkeypatch):
    """When API is not running, CLI should fail with a helpful message, not a stack trace."""
    import httpx

    def raise_connect_error(*args, **kwargs):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx.Client, "request", raise_connect_error)

    pack = tmp_path / "pack.md"
    pack.write_text("---\nfoo: bar\n---\nbody\n")
    runner = CliRunner()
    result = runner.invoke(cli, ["task", "new", str(pack)])
    assert result.exit_code != 0
    assert "cannot reach API" in result.output
