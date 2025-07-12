from pydantic import BaseModel, computed_field

from batchling.db.crud import (
    create_experiment,
    get_experiment,
    get_experiments,
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

    def retrieve(self, experiment_id: str) -> Experiment | None:
        with get_db() as db:
            experiment = get_experiment(db=db, id=experiment_id)
        if experiment is None:
            return None
        return Experiment.model_validate(experiment)

    def start_experiment(
        self,
        experiment_id: str,
        model: str,
        name: str,
        description: str | None = None,
        base_url: str | None = None,
        api_key_name: str = "OPENAI_API_KEY",
        template_messages: list[dict] | None = None,
        placeholders: list[dict] | None = None,
        response_format: BaseModel | None = None,
        input_file_path: str | None = None,
    ) -> Experiment:
        if self.retrieve(experiment_id=experiment_id) is not None:
            raise ValueError(f"Experiment with id: {experiment_id} already exists")
        with get_db() as db:
            experiment = create_experiment(
                db=db,
                id=experiment_id,
                model=model,
                name=name,
                description=description,
                base_url=base_url,
                api_key_name=api_key_name,
                template_messages=template_messages,
                placeholders=placeholders,
                response_format=response_format.model_dump()
                if response_format is not None
                else None,
                input_file_path=input_file_path,
                input_file_id=None,
                is_setup=False,
                batch_id=None,
            )
        return Experiment.model_validate(experiment)

    def update_experiment(self, experiment_id: str, **kwargs) -> Experiment:
        experiment = self.retrieve(experiment_id=experiment_id)
        return experiment.update(**kwargs)

    def delete_experiment(self, experiment_id: str) -> bool:
        experiment = self.retrieve(experiment_id=experiment_id)
        experiment.delete()
        return True
