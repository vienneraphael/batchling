from pydantic import BaseModel, computed_field

from batchling.db.crud import (
    create_experiment,
    delete_experiment,
    get_experiment,
    get_experiments,
    update_experiment,
)
from batchling.db.session import get_db, init_db
from batchling.experiment import Experiment


class ExperimentManager(BaseModel):
    def model_post_init(self, context):
        init_db()

    @computed_field
    @property
    def experiments(self) -> list[Experiment]:
        with get_db() as db:
            experiments = get_experiments(db=db)
        return [Experiment.model_validate(experiment) for experiment in experiments]

    def list_experiments(self) -> list[Experiment]:
        return self.experiments

    def retrieve(self, experiment_id: str) -> Experiment:
        with get_db() as db:
            experiment = get_experiment(db=db, id=experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        return Experiment.model_validate(experiment)

    def start_experiment(
        self,
        experiment_id: str,
        model: str,
        name: str,
        description: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        template_messages: list[dict] | None = None,
        placeholders: list[dict] | None = None,
        response_format: BaseModel | None = None,
        input_file_path: str | None = None,
    ) -> Experiment:
        with get_db() as db:
            experiment = create_experiment(
                db=db,
                id=experiment_id,
                model=model,
                name=name,
                description=description,
                base_url=base_url,
                api_key=api_key,
                template_messages=template_messages,
                placeholders=placeholders,
                response_format=response_format.model_dump()
                if response_format is not None
                else None,
                input_file_path=input_file_path,
                input_file_id=None,
                status_value="created",
                batch_id=None,
            )
        return Experiment.model_validate(experiment)

    def update_experiment(self, experiment_id: str, **kwargs) -> Experiment:
        experiment = self.retrieve(experiment_id=experiment_id)
        if experiment.status != "created":
            raise ValueError(
                f"Can only update experiments with status: created. Found: {experiment.status}"
            )
        with get_db() as db:
            updated_experiment = update_experiment(db=db, id=experiment_id, **kwargs)
        if updated_experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        return Experiment.model_validate(updated_experiment)

    def delete_experiment(self, experiment_id: str) -> bool:
        with get_db() as db:
            return delete_experiment(db=db, id=experiment_id)
