from pathlib import Path

import pytest

from batchling.db.session import destroy_db
from batchling.experiment import Experiment
from batchling.experiment_manager import ExperimentManager


@pytest.fixture
def experiment_manager():
    return ExperimentManager()


@pytest.fixture
def mock_experiment(tmp_path: Path):
    experiment_manager = ExperimentManager()
    processed_file_path = tmp_path / "processed.jsonl"
    raw_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "{greeting}, how are you {name}?"},
    ]
    placeholders = [{"name": "John", "greeting": "Hello"}]
    experiment = experiment_manager.start_experiment(
        experiment_id="em-test",
        model="gpt-4o-mini",
        name="em test",
        description="test experiment with em",
        processed_file_path=processed_file_path.as_posix(),
        raw_messages=raw_messages,
        placeholders=placeholders,
    )
    yield experiment
    destroy_db()


def test_create_experiment(mock_experiment: Experiment):
    assert mock_experiment is not None
    assert mock_experiment.created_at is not None
    assert mock_experiment.updated_at is not None
    assert mock_experiment.updated_at == mock_experiment.created_at


def test_retrieve_experiment(experiment_manager: ExperimentManager, mock_experiment: Experiment):
    retrieved_experiment = experiment_manager.retrieve(experiment_id=mock_experiment.id)
    assert retrieved_experiment is not None
    assert retrieved_experiment.__dict__ == mock_experiment.__dict__


def test_list_experiments(experiment_manager: ExperimentManager, mock_experiment: Experiment):
    experiments = experiment_manager.list_experiments()
    assert len(experiments) == 1
    assert experiments[0].__dict__ == mock_experiment.__dict__


def test_update_experiment(experiment_manager: ExperimentManager, mock_experiment: Experiment):
    updated_experiment = experiment_manager.update_experiment(
        experiment_id=mock_experiment.id, name="em test updated"
    )
    assert updated_experiment is not None
    assert updated_experiment.id == mock_experiment.id
    assert updated_experiment.__dict__ != mock_experiment.__dict__
    assert updated_experiment.updated_at != mock_experiment.updated_at


def test_update_experiment_with_invalid_status(
    experiment_manager: ExperimentManager, mock_experiment: Experiment
):
    mock_experiment.setup()
    with pytest.raises(
        ValueError,
        match="Can only update an experiment in created status. Found: setup",
    ):
        experiment_manager.update_experiment(
            experiment_id=mock_experiment.id, name="em test updated"
        )


def test_delete_experiment(experiment_manager: ExperimentManager, mock_experiment: Experiment):
    assert experiment_manager.delete_experiment(experiment_id=mock_experiment.id)
    assert experiment_manager.retrieve(experiment_id=mock_experiment.id) is None
