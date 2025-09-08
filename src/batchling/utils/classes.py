from batchling.experiment import Experiment
from batchling.providers.anthropic import AnthropicExperiment
from batchling.providers.gemini import GeminiExperiment
from batchling.providers.groq import GroqExperiment
from batchling.providers.mistral import MistralExperiment
from batchling.providers.openai import OpenAIExperiment
from batchling.providers.together import TogetherExperiment


def get_experiment_cls_from_provider(provider: str | None = None) -> type[Experiment]:
    if provider == "mistral":
        return MistralExperiment
    elif provider == "groq":
        return GroqExperiment
    elif provider == "together":
        return TogetherExperiment
    elif provider == "gemini":
        return GeminiExperiment
    elif provider == "anthropic":
        return AnthropicExperiment
    else:
        return OpenAIExperiment
