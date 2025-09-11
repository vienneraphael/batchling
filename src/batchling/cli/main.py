import json
import tomllib
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from batchling.experiment import Experiment
from batchling.experiment_manager import ExperimentManager
from batchling.request import RawRequest

app = typer.Typer(no_args_is_help=True)


def print_experiment(experiment: Experiment, status: str):
    experiment_dict = {
        "ID": experiment.id,
        "Name": experiment.name,
        "Description": experiment.description,
        "Provider": experiment.provider,
        "Endpoint": experiment.endpoint,
        "Model": experiment.model,
        "Status": f"[green]{status}[/green]",
        "Processed File Path": experiment.processed_file_path,
        "Results File Path": experiment.results_file_path,
        "Provider File ID": experiment.provider_file_id,
        "Batch ID": experiment.batch_id,
        "Created At": datetime.strftime(experiment.created_at, "%Y-%m-%d %H:%M:%S"),
        "Updated At": datetime.strftime(experiment.updated_at, "%Y-%m-%d %H:%M:%S"),
    }
    if status == "created":
        del experiment_dict["Provider File ID"]
        del experiment_dict["Batch ID"]
        if status == "created":
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
        ),
    ] = "updated_at",
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
        "Created At",
        "Updated At",
        title="Experiments",
    )
    experiments = ExperimentManager().list_experiments(order_by=order_by, ascending=ascending)
    for experiment in experiments:
        table.add_row(
            experiment.id,
            experiment.name,
            experiment.description,
            experiment.provider,
            experiment.endpoint,
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
    experiment = ExperimentManager().retrieve(experiment_id=experiment_id)
    if experiment is None:
        typer.echo(f"Experiment with id: {experiment_id} not found")
        raise typer.Exit(1)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="Retrieving experiment status from provider...", total=None)
        status = experiment.status
    print_experiment(experiment=experiment, status=status)


@app.command(name="create")
def create_experiment(
    id: Annotated[str, typer.Option(default=..., help="The id of the experiment")],
    model: Annotated[str, typer.Option(default=..., help="The model to use")],
    name: Annotated[str, typer.Option(default=..., help="The name of the experiment")],
    description: Annotated[
        str, typer.Option(default=..., help="The description of the experiment")
    ],
    provider: Annotated[
        str,
        typer.Option(
            default=...,
            help="The provider to use, e.g. openai, anthropic, gemini, groq, mistral, together..",
        ),
    ],
    endpoint: Annotated[
        str,
        typer.Option(
            default=...,
            help="The generation endpoint to use, e.g. /v1/chat/completions, /v1/embeddings..",
        ),
    ],
    processed_file_path: Annotated[
        Path,
        typer.Option(
            default=...,
            help="the batch input file path, sent to the provider. Will be used if path exists, else it will be created.",
        ),
    ],
    results_file_path: Annotated[
        Path,
        typer.Option(
            default=..., help="the path to the results file where batch results will be saved"
        ),
    ],
    raw_file_path: Annotated[
        Path | None,
        typer.Option(
            default=...,
            help="optional, the path to the raw messages file used to build the batch. Required if processed file path does not exist",
        ),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(
            help="Optional, the API key to use for the provider if not using standard naming / env variables"
        ),
    ] = None,
    response_format_path: Annotated[
        Path | None, typer.Option(help="optional, the path to the response format file")
    ] = None,
):
    """Create an experiment"""
    with open(raw_file_path, "r") as f:
        raw_requests = (
            [RawRequest.model_validate_json(line) for line in f.readlines()]
            if raw_file_path
            else None
        )
    response_format = json.load(response_format_path.open()) if response_format_path else None
    experiment = ExperimentManager().create_experiment(
        experiment_id=id,
        model=model,
        name=name,
        description=description,
        provider=provider,
        endpoint=endpoint,
        api_key=api_key,
        raw_requests=raw_requests,
        response_format=response_format,
        processed_file_path=processed_file_path.as_posix(),
        results_file_path=results_file_path.as_posix(),
    )
    print_experiment(experiment=experiment, status="created")


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
    em = ExperimentManager()
    experiment = em.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    em.start_experiment(experiment_id=id)
    print(f"Experiment with id: [green]{id}[/green] is started.")


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
    em = ExperimentManager()
    experiment = em.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    print("Downloading results..")
    em.get_results(experiment_id=id)
    print(f"Results downloaded to [green]{experiment.results_file_path}[/green]")


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
    raw_file_path: Annotated[
        Path | None, typer.Option(help="Updated template messages file path, if applicable")
    ] = None,
    processed_file_path: Annotated[
        Path | None, typer.Option(help="Updated processed file path, if applicable")
    ] = None,
    results_file_path: Annotated[
        Path | None, typer.Option(help="Updated results file path, if applicable")
    ] = None,
    provider: Annotated[str | None, typer.Option(help="Updated provider, if applicable")] = None,
    endpoint: Annotated[
        str | None,
        typer.Option(
            help="Updated generation endpoint, if applicable, e.g. /v1/chat/completions, /v1/embeddings.."
        ),
    ] = None,
    response_format_path: Annotated[
        Path | None, typer.Option(help="Updated response format file path, if applicable")
    ] = None,
):
    """Update an experiment"""
    fields_to_update = {
        key: value for key, value in ctx.params.items() if value is not None and key != "id"
    }
    em = ExperimentManager()
    experiment = em.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    old_fields = {key: getattr(experiment, key) for key in fields_to_update}
    if "raw_file_path" in fields_to_update:
        with open(fields_to_update["raw_file_path"], "r") as f:
            fields_to_update["raw_requests"] = (
                [RawRequest.model_validate_json(line) for line in f.readlines()]
                if fields_to_update["raw_file_path"]
                else None
            )
        del fields_to_update["raw_file_path"]
    if "response_format_path" in fields_to_update:
        fields_to_update["response_format"] = json.load(
            fields_to_update["response_format_path"].open()
        )
        del fields_to_update["response_format_path"]
    em.update_experiment(experiment_id=id, **fields_to_update)
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
    em = ExperimentManager()
    experiment = em.retrieve(experiment_id=id)
    if experiment is None:
        typer.echo(f"Experiment with id: {id} not found")
        raise typer.Exit(1)
    em.delete_experiment(experiment_id=id)
    print(f"Experiment with id: [green]{id}[/green] deleted")


@app.command()
def version():
    """Get the version of the package"""
    with open("pyproject.toml", "rb") as f:
        pyproject_data = tomllib.load(f)
    typer.echo(pyproject_data["project"]["version"])
    raise typer.Exit()
