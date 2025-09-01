import json
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from batchling.cli.callbacks import order_by_callback
from batchling.db.session import init_db
from batchling.experiment import Experiment
from batchling.experiment_manager import ExperimentManager
from batchling.file_utils import read_jsonl_file

app = typer.Typer(no_args_is_help=True)
init_db()

load_dotenv(override=True)


def print_experiment(experiment: Experiment):
    experiment_dict = {
        "ID": experiment.id,
        "Name": experiment.name,
        "Description": experiment.description,
        "Provider": experiment.provider,
        "Endpoint": experiment.endpoint,
        "Model": experiment.model,
        "Status": experiment.status,
        "Input File Path": experiment.input_file_path,
        "Output File Path": experiment.output_file_path,
        "Input File ID": experiment.input_file_id,
        "Batch ID": experiment.batch_id,
        "Created At": datetime.strftime(experiment.created_at, "%Y-%m-%d %H:%M:%S"),
        "Updated At": datetime.strftime(experiment.updated_at, "%Y-%m-%d %H:%M:%S"),
    }
    if experiment.status in ["setup", "created"]:
        del experiment_dict["Input File ID"]
        del experiment_dict["Batch ID"]
        if experiment.status == "created":
            del experiment_dict["Updated At"]
    values = "\n".join([f"{key}: {value}" for key, value in experiment_dict.items()])
    console = Console()
    console.print(Panel(values, title=experiment.id, expand=False, highlight=True))


def print_diff(old_fields: dict, new_fields: dict):
    values = "\n".join(
        [
            f"{key}: [yellow]{old_fields.get(key)}[/yellow] -> [green]{value}[/green]"
            for key, value in new_fields.items()
        ]
    )
    console = Console()
    console.print(Panel(values, expand=False, highlight=True))


@app.command(name="list")
def list_experiments(
    order_by: Annotated[
        str,
        typer.Option(
            "-o",
            "--order-by",
            help="The field to order by",
            rich_help_panel="Ordering",
            callback=order_by_callback,
        ),
    ] = "created_at",
    ascending: Annotated[
        bool,
        typer.Option(
            "-a/-d",
            "--ascending/--descending",
            help="Whether to order in ascending order instead of descending",
            rich_help_panel="Ordering",
        ),
    ] = False,
):
    """List experiments"""
    table = Table(
        "ID",
        "Name",
        "Description",
        "Provider",
        "Endpoint",
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
            experiment.provider,
            experiment.endpoint,
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
        ),
    ],
):
    """Get an experiment by id"""
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
    provider: Annotated[str, typer.Option(default=..., help="The provider to use")],
    endpoint: Annotated[str, typer.Option(default=..., help="The endpoint to use")],
    template_messages_path: Annotated[
        Path, typer.Option(default=..., help="The path to the template messages file")
    ],
    placeholders_path: Annotated[
        Path, typer.Option(default=..., help="The path to the placeholders file")
    ],
    input_file_path: Annotated[Path, typer.Option(default=..., help="The path to the input file")],
    output_file_path: Annotated[
        Path, typer.Option(default=..., help="The path to the output file")
    ],
    api_key_name: Annotated[str | None, typer.Option(help="The name of the API key")] = None,
    response_format_path: Annotated[
        Path | None, typer.Option(help="The path to the response format file")
    ] = None,
    max_tokens_per_request: Annotated[
        int | None, typer.Option(help="The max tokens per request to use")
    ] = None,
):
    """Create an experiment"""
    template_messages = read_jsonl_file(template_messages_path)
    placeholders = read_jsonl_file(placeholders_path)
    response_format = json.load(response_format_path.open()) if response_format_path else None
    experiment = ExperimentManager.start_experiment(
        experiment_id=id,
        model=model,
        name=name,
        description=description,
        provider=provider,
        endpoint=endpoint,
        api_key_name=api_key_name,
        template_messages=template_messages,
        placeholders=placeholders,
        response_format=response_format,
        max_tokens_per_request=max_tokens_per_request,
        input_file_path=input_file_path.as_posix(),
        output_file_path=output_file_path.as_posix(),
    )
    print_experiment(experiment)


@app.command(name="setup")
def setup_experiment(
    id: Annotated[
        str,
        typer.Argument(
            help="The id of the experiment",
        ),
    ],
):
    """Setup an experiment by writing the jsonl batch input file"""
    experiment = ExperimentManager.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    if experiment.status != "created":
        typer.echo(
            f"Experiment with id: {id} is not in created status, current status: {experiment.status}"
        )
        raise typer.Exit(1)
    experiment.setup()
    print(
        f"Experiment with id: [green]{id}[/green] is setup. Path to batch input file: [green]{experiment.input_file_path}[/green]"
    )


@app.command(name="start")
def start_experiment(
    id: Annotated[
        str,
        typer.Argument(
            help="The id of the experiment",
        ),
    ],
):
    """Start an experiment by submitting the batch to the provider"""
    experiment = ExperimentManager.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    if experiment.status != "setup":
        typer.echo(
            f"Experiment with id: {id} is not in setup status, current status: {experiment.status}"
        )
        raise typer.Exit(1)
    experiment.start()
    print(
        f"Experiment with id: [green]{id}[/green] is started. Current status is [yellow]{experiment.status}[/yellow]"
    )


@app.command(name="results")
def get_results(
    id: Annotated[
        str,
        typer.Argument(
            help="The id of the experiment",
        ),
    ],
):
    """Download the results of an experiment locally"""
    experiment = ExperimentManager.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    print("Downloading results..")
    experiment.get_results()
    print(f"Results downloaded to [green]{experiment.output_file_path}[/green]")


@app.command(name="update")
def update_experiment(
    ctx: typer.Context,
    id: Annotated[
        str,
        typer.Argument(
            help="The id of the experiment",
        ),
    ],
    model: Annotated[str | None, typer.Option(help="Updated model name, if applicable")] = None,
    name: Annotated[str | None, typer.Option(help="Updated name, if applicable")] = None,
    description: Annotated[
        str | None, typer.Option(help="Updated description, if applicable")
    ] = None,
    template_messages_path: Annotated[
        Path | None, typer.Option(help="Updated template messages file, if applicable")
    ] = None,
    placeholders_path: Annotated[
        Path | None, typer.Option(help="Updated placeholders file, if applicable")
    ] = None,
    input_file_path: Annotated[
        Path | None, typer.Option(help="Updated input file, if applicable")
    ] = None,
    output_file_path: Annotated[
        Path | None, typer.Option(help="Updated output file, if applicable")
    ] = None,
    provider: Annotated[str | None, typer.Option(help="Updated provider, if applicable")] = None,
    endpoint: Annotated[str | None, typer.Option(help="Updated endpoint, if applicable")] = None,
    response_format_path: Annotated[
        Path | None, typer.Option(help="Updated response format file, if applicable")
    ] = None,
    max_tokens_per_request: Annotated[
        int | None, typer.Option(help="Updated max tokens per request, if applicable")
    ] = None,
):
    """Update an experiment"""
    fields_to_update = {
        key: value for key, value in ctx.params.items() if value is not None and key != "id"
    }
    experiment = ExperimentManager.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    old_fields = {key: getattr(experiment, key) for key in fields_to_update}
    if "template_messages_path" in fields_to_update:
        fields_to_update["template_messages"] = read_jsonl_file(
            fields_to_update["template_messages_path"]
        )
        del fields_to_update["template_messages_path"]
    if "placeholders_path" in fields_to_update:
        fields_to_update["placeholders"] = read_jsonl_file(fields_to_update["placeholders_path"])
        del fields_to_update["placeholders_path"]
    if "response_format_path" in fields_to_update:
        fields_to_update["response_format"] = json.load(
            fields_to_update["response_format_path"].open()
        )
        del fields_to_update["response_format_path"]
    experiment.update(**fields_to_update)
    print_diff(old_fields, fields_to_update)


@app.command(name="delete")
def delete_experiment(
    id: Annotated[
        str,
        typer.Argument(
            help="The id of the experiment",
        ),
    ],
):
    """Delete an experiment"""
    experiment = ExperimentManager.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    experiment.delete()
    print(f"Experiment with id: [green]{id}[/green] deleted")


@app.command()
def version():
    """Get the version of the package"""
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)
    typer.echo(pyproject_data["project"]["version"])
    raise typer.Exit()
