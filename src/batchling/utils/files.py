import json
from pathlib import Path


def write_jsonl_file(file_path: str, data: list[str]) -> None:
    """Write a list of strings-represented JSON objects to a JSONL file

    Args:
        file_path (str): The path to the file to write
        data (list[str]): The data to write
    """
    with open(file_path, "w") as f:
        for sample in data:
            f.write(sample + "\n")


def read_jsonl_file(file_path: str | Path) -> list[dict]:
    """Read a JSONL file and return a list of strings-represented JSON objects

    Args:
        file_path (str | Path): The path to the file to read
    """
    with open(file_path, "r") as f:
        return [json.loads(line) for line in f.readlines()]
