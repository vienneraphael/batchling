from typing import Type

from batchling.experiment import Experiment, MistralExperiment, OpenAIExperiment
from batchling.request import MistralRequest, OpenAIRequest, Request


def get_experiment_cls_from_provider(provider: str | None = None) -> Type[Experiment]:
    if provider == "mistral":
        return MistralExperiment
    else:
        return OpenAIExperiment


def get_request_cls_from_provider(provider: str | None = None) -> Type[Request]:
    if provider == "mistral":
        return MistralRequest
    else:
        return OpenAIRequest
