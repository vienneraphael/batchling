import json
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from batchling.cli.callbacks import order_by_callback
from batchling.cli.completions import complete_experiment_id, complete_order_by
from batchling.db.session import init_db
from batchling.experiment import Experiment
from batchling.experiment_manager import ExperimentManager
from batchling.file_utils import read_jsonl_file

app = typer.Typer(no_args_is_help=True)
init_db()


def print_experiment(experiment: Experiment):
    values = "\n".join(
        [
            f"ID: {experiment.id}",
            f"Name: {experiment.name}",
            f"Description: {experiment.description}",
            f"Model: {experiment.model}",
            f"Status: {experiment.status}",
            f"Created At: {datetime.strftime(experiment.created_at, '%Y-%m-%d %H:%M:%S')}",
            f"Updated At: {datetime.strftime(experiment.updated_at, '%Y-%m-%d %H:%M:%S')}",
        ]
    )
    console = Console()
    console.print(Panel(values, title=experiment.id, expand=False, highlight=True))


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
    experiments = ExperimentManager.list_experiments(order_by=order_by, ascending=ascending)
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


@app.command(name="get")
def get_experiment(
    experiment_id: Annotated[
        str,
        typer.Argument(
            help="The id of the experiment",
            autocompletion=complete_experiment_id,
        ),
    ],
):
    experiment = ExperimentManager.retrieve(experiment_id=experiment_id)
    if experiment is None:
        typer.echo(f"Experiment with id: {experiment_id} not found")
        raise typer.Exit(1)
    print_experiment(experiment)


@app.command(name="create")
def create_experiment(
    id: Annotated[str, typer.Option(default=..., help="The id of the experiment")],
    model: Annotated[str, typer.Option(default=..., help="The model to use")],
    name: Annotated[str, typer.Option(default=..., help="The name of the experiment")],
    description: Annotated[
        str, typer.Option(default=..., help="The description of the experiment")
    ],
    template_messages_path: Annotated[
        Path, typer.Option(default=..., help="The path to the template messages file")
    ],
    placeholders_path: Annotated[
        Path, typer.Option(default=..., help="The path to the placeholders file")
    ],
    input_file_path: Annotated[Path, typer.Option(default=..., help="The path to the input file")],
    response_format_path: Annotated[
        Path, typer.Option(default=..., help="The path to the response format file")
    ],
):
    template_messages = read_jsonl_file(template_messages_path)
    placeholders = read_jsonl_file(placeholders_path)
    response_format = json.load(response_format_path.open())
    experiment = ExperimentManager.start_experiment(
        experiment_id=id,
        model=model,
        name=name,
        description=description,
        template_messages=template_messages,
        placeholders=placeholders,
        response_format=response_format,
        input_file_path=input_file_path.as_posix(),
    )
    print_experiment(experiment)


@app.command(name="setup")
def setup_experiment(
    id: Annotated[
        str,
        typer.Argument(
            default=...,
            help="The id of the experiment",
            autocompletion=complete_experiment_id,
        ),
    ],
):
    experiment = ExperimentManager.retrieve(experiment_id=id)
    if experiment.status != "created":
        typer.echo(
            f"Experiment with id: {id} is not in created status, current status: {experiment.status}"
        )
        raise typer.Exit(1)
    experiment.setup()
    print_experiment(experiment)


@app.command(name="start")
def start_experiment(
    id: Annotated[str, typer.Option(default=..., help="The id of the experiment")],
):
    pass


@app.command(name="update")
def update_experiment(
    id: Annotated[str, typer.Option(default=..., help="The id of the experiment")],
):
    pass


@app.command(name="delete")
def delete_experiment(
    id: Annotated[str, typer.Option(default=..., help="The id of the experiment")],
):
    pass


@app.command()
def version():
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)
    typer.echo(pyproject_data["project"]["version"])
    raise typer.Exit()
