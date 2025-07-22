from typing import Type

from batchling.experiment import Experiment, OpenAIExperiment


def get_cls_from_url(base_url: str | None = None) -> Type[Experiment]:
    if base_url:
        return OpenAIExperiment
    else:
        return OpenAIExperiment
