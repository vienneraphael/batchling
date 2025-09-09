import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel

from batchling.db.session import destroy_db
from batchling.experiment import Experiment
from batchling.experiment_manager import ExperimentManager
from batchling.request import RawMessage, RawRequest


class City(BaseModel):
    name: str
    country: str


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
def mock_client(provider):
    match provider:
        case "openai":
            with patch("openai.OpenAI") as OpenAI_cls:
                client = MagicMock(name="openai_client")
                file_obj = MagicMock(name="fake_file", id="test-file-id")
                client.files.create.return_value = file_obj
                batch_obj = MagicMock(name="fake_batch", id="test-batch-id")
                client.batches.create.return_value = batch_obj
                OpenAI_cls.return_value = client
                yield client
        case "mistral":
            with patch("mistralai.Mistral") as Mistral_cls:
                client = MagicMock(name="mistral_client")
                file_obj = MagicMock(name="fake_file", id="test-file-id")
                client.files.upload.return_value = file_obj
                batch_obj = MagicMock(name="fake_batch", id="test-batch-id")
                client.batch.jobs.create.return_value = batch_obj
                Mistral_cls.return_value = client
                yield client
        case "together":
            with patch("together.Together") as Together_cls:
                client = MagicMock(name="together_client")
                file_obj = MagicMock(name="fake_file", id="test-file-id")
                client.files.upload.return_value = file_obj
                batch_obj = MagicMock(name="fake_batch", id="test-batch-id")
                client.batches.create_batch.return_value = batch_obj
                Together_cls.return_value = client
                yield client
        case "groq":
            with patch("groq.Groq") as Groq_cls:
                client = MagicMock(name="groq_client")
                file_obj = MagicMock(name="fake_file", id="test-file-id")
                client.files.create.return_value = file_obj
                batch_obj = MagicMock(name="fake_batch", id="test-batch-id")
                client.batches.create.return_value = batch_obj
                Groq_cls.return_value = client
                yield client
        case "gemini":
            with patch("google.genai.Client") as Gemini_cls:
                client = MagicMock(name="gemini_client")
                file_obj = MagicMock(name="fake_file")
                file_obj.name = "test-file-id"
                client.files.upload.return_value = file_obj
                batch_obj = MagicMock(name="fake_batch")
                batch_obj.name = "test-batch-id"
                client.batches.create.return_value = batch_obj
                Gemini_cls.return_value = client
                yield client
        case "anthropic":
            with patch("anthropic.Anthropic") as Anthropic_cls:
                client = MagicMock(name="anthropic_client")
                batch_obj = MagicMock(name="fake_batch", id="test-batch-id")
                client.messages.batches.create.return_value = batch_obj
                Anthropic_cls.return_value = client
                yield client
        case _:
            raise ValueError(f"Invalid provider: {provider}")


@pytest.fixture
def experiment_manager():
    return ExperimentManager()


@pytest.fixture
def experiment(
    experiment_manager: ExperimentManager,
    tmp_path: Path,
    provider: str,
    structured_output: tuple[str, dict],
):
    name, response_format = structured_output
    processed_file_path = tmp_path / "processed.jsonl"
    results_file_path = tmp_path / "results.jsonl"
    raw_requests = [
        RawRequest(
            messages=[
                RawMessage(role="user", content="Hello, how are you Dan?"),
            ],
            max_tokens=100,
        ),
    ]
    experiment = experiment_manager.create_experiment(
        experiment_id=f"em-test-{provider}-{name}",
        model="gpt-4o-mini",
        name="em test",
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
def started_experiment(experiment: Experiment, mock_client):
    experiment.client = mock_client
    experiment.start()
    return experiment


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
    retrieved_experiment = experiment_manager.retrieve(experiment_id=experiment.id)
    assert retrieved_experiment is not None
    assert retrieved_experiment.model_dump() == experiment.model_dump()


def test_list_experiments(experiment_manager: ExperimentManager, experiment: Experiment):
    experiments = experiment_manager.list_experiments()
    assert len(experiments) == 1
    assert experiments[0].model_dump() == experiment.model_dump()


def test_update_experiment(experiment_manager: ExperimentManager, experiment: Experiment):
    updated_experiment = experiment_manager.update_experiment(
        experiment_id=experiment.id, name="em test updated"
    )
    assert updated_experiment is not None
    assert updated_experiment.id == experiment.id
    assert updated_experiment.model_dump() != experiment.model_dump()
    assert updated_experiment.updated_at != experiment.updated_at


def test_delete_experiment(experiment_manager: ExperimentManager, experiment: Experiment):
    assert experiment_manager.delete_experiment(experiment_id=experiment.id)
    assert experiment_manager.retrieve(experiment_id=experiment.id) is None
