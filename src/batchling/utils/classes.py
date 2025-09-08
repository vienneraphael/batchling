from batchling.experiment import Experiment


def get_experiment_cls_from_provider(provider: str | None = None) -> type[Experiment]:
    if provider == "mistral":
        from batchling.providers.mistral import MistralExperiment

        return MistralExperiment
    elif provider == "groq":
        from batchling.providers.groq import GroqExperiment

        return GroqExperiment
    elif provider == "together":
        from batchling.providers.together import TogetherExperiment

        return TogetherExperiment
    elif provider == "gemini":
        from batchling.providers.gemini import GeminiExperiment

        return GeminiExperiment
    elif provider == "anthropic":
        from batchling.providers.anthropic import AnthropicExperiment

        return AnthropicExperiment
    else:
        from batchling.providers.openai import OpenAIExperiment

        return OpenAIExperiment
