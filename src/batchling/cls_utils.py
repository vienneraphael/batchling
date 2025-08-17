from typing import Type

from batchling.experiment import (
    Experiment,
    GroqExperiment,
    MistralExperiment,
    OpenAIExperiment,
)


def get_experiment_cls_from_provider(provider: str | None = None) -> Type[Experiment]:
    if provider == "mistral":
        return MistralExperiment
    elif provider == "groq":
        return GroqExperiment
    else:
        return OpenAIExperiment
