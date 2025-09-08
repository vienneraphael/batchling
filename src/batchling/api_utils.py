"""API utils"""

import os


def get_default_api_key_from_provider(provider: str) -> str:
    api_key = os.getenv(f"{provider.upper()}_API_KEY")
    if not api_key:
        raise ValueError(
            f"API key not found for provider: {provider}. Either set the API key in the environment variables or provide it through the api_key parameter."
        )
    return api_key
