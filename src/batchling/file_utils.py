def write_jsonl_file(file_path: str, data: list[str]) -> None:
    """Write a list of strings-represented JSON objects to a JSONL file

    Args:
        file_path (str): The path to the file to write
        data (list[str]): The data to write
    """
    with open(file_path, "w") as f:
        for sample in data[:-1]:
            f.write(sample + "\n")
        f.write(data[-1])
