from dotenv import load_dotenv
from pydantic import BaseModel, computed_field

from batchling.api_utils import get_default_api_key_name_from_provider
from batchling.cls_utils import get_experiment_cls_from_provider
from batchling.db.crud import (
    create_experiment,
    get_experiment,
    get_experiments,
)
from batchling.db.session import get_db, init_db
from batchling.experiment import Experiment


class ExperimentManager(BaseModel):
    def model_post_init(self, context):
        load_dotenv(override=True)
        init_db()

    @computed_field
    @property
    def experiments(self) -> list[Experiment]:
        return self.list_experiments()

    @staticmethod
    def list_experiments(
        order_by: str | None = "updated_at",
        ascending: bool = False,
        limit: int | None = None,
        offset: int | None = None,
        filter_by: str | None = None,
        filter_value: str | None = None,
        starts_with_field: str | None = None,
        starts_with: str | None = None,
    ) -> list[Experiment]:
        with get_db() as db:
            experiments = get_experiments(
                db=db,
                order_by=order_by,
                ascending=ascending,
                limit=limit,
                offset=offset,
                filter_by=filter_by,
                filter_value=filter_value,
                starts_with_field=starts_with_field,
                starts_with=starts_with,
            )
        return [
            get_experiment_cls_from_provider(experiment.provider).model_validate(experiment)
            for experiment in experiments
        ]

    @staticmethod
    def retrieve(experiment_id: str) -> Experiment | None:
        with get_db() as db:
            experiment = get_experiment(db=db, id=experiment_id)
        if experiment is None:
            return None
        return get_experiment_cls_from_provider(experiment.provider).model_validate(experiment)

    @staticmethod
    def start_experiment(
        experiment_id: str,
        model: str,
        name: str,
        api_key_name: str | None = None,
        description: str | None = None,
        provider: str = "openai",
        endpoint: str = "/v1/chat/completions",
        template_messages: list[dict] | None = None,
        placeholders: list[dict] | None = None,
        response_format: BaseModel | dict | None = None,
        max_tokens_per_request: int | None = None,
        input_file_path: str | None = None,
        output_file_path: str = "results.jsonl",
    ) -> Experiment:
        if ExperimentManager.retrieve(experiment_id=experiment_id) is not None:
            raise ValueError(f"Experiment with id: {experiment_id} already exists")
        if isinstance(response_format, BaseModel):
            response_format = response_format.model_dump()
        with get_db() as db:
            experiment = create_experiment(
                db=db,
                id=experiment_id,
                model=model,
                name=name,
                description=description,
                provider=provider,
                endpoint=endpoint,
                api_key_name=api_key_name or get_default_api_key_name_from_provider(provider),
                template_messages=template_messages,
                placeholders=placeholders,
                response_format=response_format,
                max_tokens_per_request=max_tokens_per_request,
                input_file_path=input_file_path,
                output_file_path=output_file_path,
            )
        return get_experiment_cls_from_provider(experiment.provider).model_validate(experiment)

    @staticmethod
    def update_experiment(experiment_id: str, **kwargs) -> Experiment:
        experiment = ExperimentManager.retrieve(experiment_id=experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        return experiment.update(**kwargs)

    @staticmethod
    def delete_experiment(experiment_id: str) -> bool:
        experiment = ExperimentManager.retrieve(experiment_id=experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        experiment.delete()
        return True
