from datetime import datetime

import pytest

from batchling.experiment import Experiment
from batchling.providers.openai import OpenAIExperiment
from batchling.request import RawMessage, RawRequest
from batchling.utils.api import get_default_api_key_from_provider


@pytest.fixture
def experiment(tmp_path):
    raw_requests = [
        RawRequest(
            messages=[
                RawMessage(role="user", content="Hello, how are you Dan?"),
            ],
            max_tokens=100,
        ),
    ]
    now = datetime.now()
    api_key = get_default_api_key_from_provider(provider="openai")
    experiment = OpenAIExperiment(
        id="experiment-test-1",
        model="gpt-4o-mini",
        title="test 1",
        description="test experiment number 1",
        processed_file_path=(tmp_path / "test.jsonl").as_posix(),
        raw_requests=raw_requests,
        api_key=api_key,
        created_at=now,
        updated_at=now,
    )
    return experiment


def test_invalid_processed_file_path():
    with pytest.raises(ValueError, match="processed_file_path must be a .jsonl file"):
        OpenAIExperiment(
            id="experiment-test-2",
            model="gpt-4o-mini",
            title="test 1",
            description="test experiment number 1",
            processed_file_path="test.txt",
        )


def test_cancel_without_start(experiment: Experiment):
    with pytest.raises(
        ValueError,
        match=r"Experiment in status created is not in .*",
    ):
        experiment.cancel()
