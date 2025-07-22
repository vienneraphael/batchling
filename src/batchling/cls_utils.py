from typing import Type

from batchling.experiment import Experiment, MistralExperiment, OpenAIExperiment


def get_cls_from_url(provider: str | None = None) -> Type[Experiment]:
    if provider == "mistral":
        return MistralExperiment
    else:
        return OpenAIExperiment
