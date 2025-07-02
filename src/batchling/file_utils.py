import json


def write_jsonl_file(file_path: str, data: list[dict]) -> None:
    """Write a list of dictionaries to a JSONL file

    Args:
        file_path (str): The path to the file to write
        data (list[dict]): The data to write
    """
    with open(file_path, "w") as f:
        for sample in data[:-1]:
            f.write(json.dumps(sample) + "\n")
        f.write(json.dumps(data[-1]) + "\n")
