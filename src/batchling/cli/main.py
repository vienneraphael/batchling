import tomllib
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from batchling.cli.callbacks import order_by_callback
from batchling.cli.completions import complete_order_by
from batchling.db.session import init_db
from batchling.experiment_manager import ExperimentManager

app = typer.Typer(no_args_is_help=True)


@app.callback()
def callback():
    init_db()


@app.command(name="list")
def list_experiments(
    order_by: Annotated[
        str,
        typer.Option(
            "-o",
            "--order-by",
            help="The field to order by",
            rich_help_panel="Ordering",
            autocompletion=complete_order_by,
            callback=order_by_callback,
        ),
    ] = "created_at",
    ascending: Annotated[
        bool,
        typer.Option(
            "-a/-d",
            "--ascending/--descending",
            help="Whether to order in ascending order instead of descending",
            is_flag=True,
            rich_help_panel="Ordering",
        ),
    ] = False,
):
    """List experiments"""
    table = Table(
        "ID",
        "Name",
        "Description",
        "Status",
        "Created At",
        "Updated At",
        title="Experiments",
    )
    em = ExperimentManager()
    experiments = em.list_experiments(order_by=order_by, ascending=ascending)
    for experiment in experiments:
        table.add_row(
            experiment.id,
            experiment.name,
            experiment.description,
            experiment.status,
            datetime.strftime(experiment.created_at, "%Y-%m-%d %H:%M:%S"),
            datetime.strftime(experiment.updated_at, "%Y-%m-%d %H:%M:%S"),
        )
    console = Console()
    console.print(table)


@app.command()
def version():
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)
    typer.echo(pyproject_data["project"]["version"])
    raise typer.Exit()
