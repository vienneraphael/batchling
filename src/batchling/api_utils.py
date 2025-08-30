"""API utils"""


def get_default_api_key_name_from_provider(provider: str | None = None) -> str:
    if provider == "mistral":
        return "MISTRAL_API_KEY"
    elif provider == "groq":
        return "GROQ_API_KEY"
    elif provider == "together":
        return "TOGETHER_API_KEY"
    elif provider == "gemini":
        return "GEMINI_API_KEY"
    elif provider == "anthropic":
        return "ANTHROPIC_API_KEY"
    else:
        return "OPENAI_API_KEY"
