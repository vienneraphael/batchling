from typing import Type

from batchling.experiment import Experiment
from batchling.providers.groq import GroqExperiment
from batchling.providers.mistral import MistralExperiment
from batchling.providers.openai import OpenAIExperiment
from batchling.providers.together import TogetherExperiment


def get_experiment_cls_from_provider(provider: str | None = None) -> Type[Experiment]:
    if provider == "mistral":
        return MistralExperiment
    elif provider == "groq":
        return GroqExperiment
    elif provider == "together":
        return TogetherExperiment
    else:
        return OpenAIExperiment
