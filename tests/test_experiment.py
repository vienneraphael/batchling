import os
from unittest.mock import MagicMock, patch

import pytest

from batchling.cls_utils import get_experiment_cls_from_provider
from batchling.db.crud import get_experiment
from batchling.db.session import get_db
from batchling.experiment import Experiment
from batchling.providers.openai import OpenAIExperiment


@pytest.fixture(params=["openai", "mistral", "together"])
def provider(request):
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
        case _:
            raise ValueError(f"Invalid provider: {provider}")


@pytest.fixture
def experiment(tmp_path, provider):
    template_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "{greeting}, how are you {name}?"},
    ]
    placeholders = [{"name": "John", "greeting": "Hello"}]
    experiment_cls = get_experiment_cls_from_provider(provider)
    experiment = experiment_cls.model_validate(
        {
            "id": f"{provider}-experiment-test-1",
            "model": "gpt-4o-mini",
            "name": "test 1",
            "description": "test experiment number 1",
            "input_file_path": (tmp_path / "test.jsonl").as_posix(),
            "template_messages": template_messages,
            "placeholders": placeholders,
        }
    )
    return experiment


@pytest.fixture
def setup_experiment(experiment: Experiment):
    experiment.setup()
    return experiment


@pytest.fixture
def started_experiment(setup_experiment: Experiment, mock_client):
    setup_experiment.client = mock_client
    setup_experiment.start()
    return setup_experiment


def test_invalid_input_file_path():
    with pytest.raises(ValueError, match="input_file_path must be a .jsonl file"):
        OpenAIExperiment(
            id="experiment-test-1",
            model="gpt-4o-mini",
            name="test 1",
            description="test experiment number 1",
            input_file_path="test.txt",
        )


def test_double_setup(setup_experiment: Experiment):
    with pytest.raises(
        ValueError,
        match="Experiment in status setup is not in created status",
    ):
        setup_experiment.setup()


def test_setup(setup_experiment: Experiment):
    assert setup_experiment.is_setup
    assert os.path.exists(setup_experiment.input_file_path)


def test_start_without_setup(experiment: Experiment):
    with pytest.raises(
        ValueError,
        match="Experiment in status created is not in setup status",
    ):
        experiment.start()


def test_start(started_experiment: Experiment):
    assert started_experiment.batch is not None
    assert started_experiment.input_file is not None


def test_cancel_without_start(setup_experiment: Experiment):
    with pytest.raises(
        ValueError,
        match=r"Experiment in status setup is not in .*",
    ):
        setup_experiment.cancel()


def test_save(experiment: Experiment):
    experiment.save()
    with get_db() as db:
        assert get_experiment(db=db, id=experiment.id) is not None


def test_delete(experiment: Experiment):
    experiment.delete()
    with get_db() as db:
        assert get_experiment(db=db, id=experiment.id) is None


def test_update(experiment: Experiment):
    experiment.save()
    experiment.update(name="test 1 updated")
    with get_db() as db:
        updated_experiment = get_experiment(db=db, id=experiment.id)
        assert experiment.__dict__ != updated_experiment.__dict__
