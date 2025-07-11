import pytest

from batchling.experiment import Experiment, ExperimentStatus


@pytest.fixture
def experiment():
    return Experiment(
        id="experiment-test-1",
        model="gpt-4o-mini",
        name="test 1",
        description="test experiment number 1",
    )


def test_invalid_input_file_path():
    with pytest.raises(ValueError, match="input_file_path must be a .jsonl file"):
        Experiment(
            id="experiment-test-1",
            model="gpt-4o-mini",
            name="test 1",
            description="test experiment number 1",
            input_file_path="test.txt",
        )


def test_setup(tmp_path):
    template_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "{greeting}, how are you {name}?"},
    ]
    placeholders = [{"name": "John", "greeting": "Hello"}]
    experiment = Experiment(
        id="experiment-test-1",
        model="gpt-4o-mini",
        name="test 1",
        description="test experiment number 1",
        input_file_path=(tmp_path / "test.jsonl").as_posix(),
        template_messages=template_messages,
        placeholders=placeholders,
    )
    experiment.setup()
    assert experiment.status == ExperimentStatus.SETUP


def test_start_without_setup():
    with pytest.raises(ValueError, match="Experiment in status created is not in setup status"):
        experiment = Experiment(
            id="experiment-test-1",
            model="gpt-4o-mini",
            name="test 1",
            description="test experiment number 1",
        )
        experiment.start()
