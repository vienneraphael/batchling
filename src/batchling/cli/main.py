import asyncio
import inspect
import runpy
import typing as t
from pathlib import Path

import typer

from batchling import DeferredExit, batchify
from batchling.exceptions import is_deferred_exit_error

# syncify = lambda f: wraps(f)(lambda *args, **kwargs: asyncio.run(f(*args, **kwargs)))


app = typer.Typer(
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)


def parse_function_call_args(script_args: list[str]) -> tuple[list[str], dict[str, t.Any]]:
    """
    Parse script arguments into positional and keyword function arguments.

    Parameters
    ----------
    script_args : list[str]
        Raw CLI arguments forwarded to the target callable.

    Returns
    -------
    tuple[list[str], dict[str, typing.Any]]
        Tuple of positional arguments and keyword arguments.
    """
    positional_args: list[str] = []
    keyword_args: dict[str, t.Any] = {}
    index = 0
    while index < len(script_args):
        argument = script_args[index]
        if not argument.startswith("--") or argument == "--":
            positional_args.append(argument)
            index += 1
            continue

        option = argument[2:]
        if not option:
            raise typer.BadParameter("Invalid option '--'")

        if "=" in option:
            option_name, option_value = option.split("=", 1)
        else:
            option_name = option
            next_value_index = index + 1
            if next_value_index < len(script_args) and not script_args[next_value_index].startswith(
                "--"
            ):
                option_value = script_args[next_value_index]
                index += 1
            else:
                option_value = True

        keyword_args[option_name.replace("-", "_")] = option_value
        index += 1

    return positional_args, keyword_args


async def run_script_with_batchify(
    module_path: Path,
    func_name: str,
    script_args: list[str],
    batch_size: int,
    batch_window_seconds: float,
    batch_poll_interval_seconds: float,
    dry_run: bool,
    cache: bool,
    deferred: bool,
    deferred_idle_seconds: float,
):
    """
    Execute a Python script under a batchify context.

    Parameters
    ----------
    module_path : Path
        Path to the Python script to execute.
    func_name : str
        Name of the function to execute.
    script_args : list[str]
        Arguments forwarded to the script as ``sys.argv[1:]``.
    batch_size : int
        Batch size passed to ``batchify``.
    batch_window_seconds : float
        Batch window passed to ``batchify``.
    batch_poll_interval_seconds : float
        Polling interval passed to ``batchify``.
    dry_run : bool
        Dry run mode passed to ``batchify``.
    cache : bool
        Cache mode passed to ``batchify``.
    deferred : bool
        Deferred mode passed to ``batchify``.
    deferred_idle_seconds : float
        Deferred idle threshold passed to ``batchify``.
    """
    if not module_path.exists():
        typer.echo(f"Script not found: {module_path}")
        raise typer.Exit(1)
    if not module_path.is_file():
        typer.echo(f"Script path is not a file: {module_path}")
        raise typer.Exit(1)

    script_path_as_posix = module_path.resolve().as_posix()
    async with batchify(
        batch_size=batch_size,
        batch_window_seconds=batch_window_seconds,
        batch_poll_interval_seconds=batch_poll_interval_seconds,
        dry_run=dry_run,
        cache=cache,
        deferred=deferred,
        deferred_idle_seconds=deferred_idle_seconds,
    ):
        ns = runpy.run_path(path_name=script_path_as_posix, run_name="batchling.runtime")
        func = ns.get(func_name)
        if func is None:
            raise ValueError(f"Function {func_name} not found in script {script_path_as_posix}")
        if not inspect.iscoroutinefunction(func):
            raise ValueError(f"Function {func_name} is not an async function")
        positional_args, keyword_args = parse_function_call_args(script_args=script_args)
        await func(*positional_args, **keyword_args)


@app.command(
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
)
def main(
    ctx: typer.Context,
    script_path: t.Annotated[
        Path,
        typer.Argument(help="Path to the Python script to run with batching enabled"),
    ],
    batch_size: t.Annotated[
        int,
        typer.Option(help="Submit a batch when this many requests are queued"),
    ] = 50,
    batch_window_seconds: t.Annotated[
        float,
        typer.Option(help="Submit a batch after this many seconds"),
    ] = 2.0,
    batch_poll_interval_seconds: t.Annotated[
        float,
        typer.Option(help="Poll active provider batches every this many seconds"),
    ] = 10.0,
    dry_run: t.Annotated[
        bool,
        typer.Option(help="Intercept and batch requests without sending provider batches"),
    ] = False,
    cache: t.Annotated[
        bool,
        typer.Option("--cache/--no-cache", help="Enable persistent request caching"),
    ] = True,
    deferred: t.Annotated[
        bool,
        typer.Option(help="Allow deferred-mode idle termination while polling"),
    ] = False,
    deferred_idle_seconds: t.Annotated[
        float,
        typer.Option(help="Deferred-mode idle threshold in seconds"),
    ] = 60.0,
):
    """Run a script under ``batchify``."""
    try:
        module_path, func_name = script_path.as_posix().rsplit(":", 1)
    except ValueError:
        raise typer.BadParameter("Script path must be a module path, use 'module:func' syntax")
    script_args = list(ctx.args)

    try:
        asyncio.run(
            run_script_with_batchify(
                module_path=Path(module_path),
                func_name=func_name,
                script_args=script_args,
                batch_size=batch_size,
                batch_window_seconds=batch_window_seconds,
                batch_poll_interval_seconds=batch_poll_interval_seconds,
                dry_run=dry_run,
                cache=cache,
                deferred=deferred,
                deferred_idle_seconds=deferred_idle_seconds,
            )
        )
    except DeferredExit:
        typer.echo(
            "Deferred mode: batches are underway. Re-run this command later to fetch results."
        )
        raise typer.Exit(code=0)
    except Exception as error:
        if is_deferred_exit_error(error=error):
            typer.echo(
                "Deferred mode: batches are underway. Re-run this command later to fetch results."
            )
            raise typer.Exit(code=0)
        raise
