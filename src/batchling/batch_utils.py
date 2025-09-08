def split_system_instructions_and_messages(messages: list[dict]) -> tuple[dict | None, list[dict]]:
    """Split the system instructions and messages from the messages

    Args:
        messages (list[dict]): The messages to split the system instructions and messages from

    Returns:
        tuple[dict | None, list[dict]]: The system instructions and messages
    """
    if messages[0]["role"] == "system":
        system_instructions = messages[0]
        messages = messages[1:]
    else:
        system_instructions = None
    return system_instructions, messages
