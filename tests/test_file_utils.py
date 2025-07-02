import os

import pytest

from batchling.file_utils import write_jsonl_file


@pytest.fixture
def mock_data():
    return [
        {"id": 1, "name": "John"},
        {"id": 2, "name": "Jane"},
    ]


def test_write_jsonl_file(tmp_path, mock_data):
    file_path = tmp_path / "test.jsonl"
    write_jsonl_file(file_path=file_path, data=mock_data)
    assert os.path.exists(file_path)
    assert os.path.getsize(file_path) > 0
