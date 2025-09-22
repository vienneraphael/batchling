from batchling.cli.enums import OrderByFields, Provider
from batchling.experiment_manager import ExperimentManager


def complete_order_by(value: str):
    for field in OrderByFields.__members__.values():
        if field.startswith(value):
            yield field


def complete_provider(value: str):
    for provider in Provider.__members__.values():
        if provider.startswith(value):
            yield provider


def complete_experiment_name(value: str):
    for experiment in ExperimentManager.list_experiments(
        order_by="name",
        ascending=True,
        limit=5,
        starts_with_field="name",
        starts_with=value,
    ):
        yield experiment.name
