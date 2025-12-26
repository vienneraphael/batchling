import os
from pathlib import Path

import pytest
from pydantic import BaseModel

from batchling.db.session import destroy_db
from batchling.experiment import Experiment
from batchling.experiment_manager import ExperimentManager
from batchling.request import raw_request_list_adapter
from batchling.utils.files import read_jsonl_file


class City(BaseModel):
    name: str
    country: str


@pytest.fixture(
    params=["tests/test_data/raw_file_countries.jsonl", "tests/test_data/raw_file_multimodal.jsonl"]
)
def raw_requests_file_path(request, provider: str):
    file_path = request.param
    if provider == "anthropic":
        # Replace .jsonl with _anthropic.jsonl
        file_path = file_path.replace(".jsonl", "_anthropic.jsonl")
    return file_path


@pytest.fixture(params=["openai", "mistral", "together", "groq", "gemini", "anthropic"])
def provider(request):
    return request.param


@pytest.fixture(
    params=[
        ("None", dict()),
        (
            "json",
            {
                "type": "json_schema",
                "json_schema": {
                    "schema": {
                        "properties": {
                            "name": {
                                "description": "the city name",
                                "title": "Name",
                                "type": "string",
                            },
                            "country": {
                                "description": "the country of the city",
                                "title": "Country",
                                "type": "string",
                            },
                        },
                        "required": ["name", "country"],
                        "title": "City",
                        "type": "object",
                        "additionalProperties": False,
                    },
                    "name": "City",
                    "strict": True,
                },
            },
        ),
        (
            "pydantic",
            {
                "type": "json_schema",
                "json_schema": {
                    "schema": City.model_json_schema(),
                    "name": City.__name__,
                    "strict": True,
                },
            },
        ),
    ]
)
def structured_output(request):
    return request.param


@pytest.fixture
def experiment_manager():
    return ExperimentManager()


@pytest.fixture
def experiment(
    experiment_manager: ExperimentManager,
    tmp_path: Path,
    provider: str,
    structured_output: tuple[str, dict],
    raw_requests_file_path: str,
):
    raw_requests = read_jsonl_file(raw_requests_file_path)
    name, response_format = structured_output
    processed_file_path = tmp_path / "processed.jsonl"
    results_file_path = tmp_path / "results.jsonl"
    raw_requests = raw_request_list_adapter.validate_python(raw_requests)
    experiment = experiment_manager.create_experiment(
        experiment_name=f"em-test-{provider}-{name}",
        model="gpt-4o-mini",
        title="em test",
        provider=provider,
        description="test experiment with em",
        processed_file_path=processed_file_path.as_posix(),
        response_format=response_format,
        raw_requests=raw_requests,
        results_file_path=results_file_path.as_posix(),
    )
    yield experiment
    destroy_db()


@pytest.fixture
def started_experiment(experiment_manager: ExperimentManager, experiment: Experiment):
    return experiment_manager.start_experiment(experiment_name=experiment.name)


def test_start(started_experiment: Experiment):
    assert started_experiment.batch is not None
    assert started_experiment.provider_file is not None


def test_processed_file_path(experiment: Experiment):
    assert os.path.exists(experiment.processed_file_path)


def test_create_experiment(experiment: Experiment):
    assert experiment is not None
    assert experiment.created_at is not None
    assert experiment.updated_at is not None
    assert experiment.updated_at == experiment.created_at


def test_retrieve_experiment(experiment_manager: ExperimentManager, experiment: Experiment):
    retrieved_experiment = experiment_manager.retrieve(experiment_name=experiment.name)
    assert retrieved_experiment is not None
    assert retrieved_experiment.model_dump() == experiment.model_dump()


def test_list_experiments(experiment_manager: ExperimentManager, experiment: Experiment):
    experiments = experiment_manager.list_experiments()
    assert len(experiments) == 1
    assert experiments[0].model_dump() == experiment.model_dump()


def test_update_experiment(experiment_manager: ExperimentManager, experiment: Experiment):
    update_dict = {"title": "em test updated"}
    updated_experiment = experiment_manager.update_experiment(
        experiment_name=experiment.name, kwargs=update_dict
    )
    assert updated_experiment is not None
    assert updated_experiment.name == experiment.name
    assert updated_experiment.model_dump() != experiment.model_dump()
    assert updated_experiment.updated_at != experiment.updated_at


def test_delete_experiment(experiment_manager: ExperimentManager, experiment: Experiment):
    experiment_manager.delete_experiment(experiment_name=experiment.name)
    assert experiment_manager.retrieve(experiment_name=experiment.name) is None


def test_get_results_parsing(experiment_manager: ExperimentManager, started_experiment: Experiment):
    results = experiment_manager.get_results(experiment_name=started_experiment.name)
    assert isinstance(results, list)
    assert len(results) == 2
    for item in results:
        # Unified BatchResult fields should be populated
        assert item.id is not None
        assert item.custom_id is not None
        assert item.answer is not None
        assert item.model is not None
        assert item.original is not None
