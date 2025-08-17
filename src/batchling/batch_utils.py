import copy


def replace_placeholders(messages: list[dict], placeholder_dict: dict) -> list[dict]:
    """Replace the placeholders in the messages

    Args:
        messages (list[dict]): The messages to replace the placeholders in
        placeholder_dict (dict): The placeholder to replace in the messages

    Returns:
        list[dict]: The messages with the placeholders replaced
    """
    messages_copy = copy.deepcopy(messages)
    for message in messages_copy:
        if message["role"] == "user":
            content = message["content"]
            if isinstance(content, str):
                message["content"] = content.format(**placeholder_dict)
            elif isinstance(content, list):
                for item in content:
                    item["text"] = item["text"].format(**placeholder_dict)
            else:
                raise ValueError(f"Invalid content type: {type(content)}")
    return messages_copy
