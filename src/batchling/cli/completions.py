from batchling.cli.enums import OrderByFields
from batchling.experiment_manager import ExperimentManager


def complete_order_by(value: str):
    for field in OrderByFields.__members__.values():
        if field.startswith(value):
            yield field


def complete_experiment_id(value: str):
    for experiment in ExperimentManager.list_experiments(
        order_by="id",
        ascending=True,
        limit=10,
        starts_with_field="id",
        starts_with=value,
    ):
        yield experiment.id
