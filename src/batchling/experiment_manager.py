import os

from dotenv import load_dotenv
from pydantic import BaseModel, computed_field

from batchling.db.session import get_db, init_db
from batchling.experiment import Experiment
from batchling.request import RawRequest
from batchling.utils.api import get_default_api_key_from_provider
from batchling.utils.classes import get_experiment_cls_from_provider


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
        from batchling.db.crud import get_experiments

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
        for experiment in experiments:
            experiment.raw_requests = (
                [RawRequest.model_validate(raw_request) for raw_request in experiment.raw_requests]
                if experiment.raw_requests
                else None
            )
        return [
            get_experiment_cls_from_provider(experiment.provider).model_validate(experiment)
            for experiment in experiments
        ]

    @staticmethod
    def retrieve(experiment_id: str) -> Experiment | None:
        from batchling.db.crud import get_experiment

        with get_db() as db:
            experiment = get_experiment(db=db, id=experiment_id)
        if experiment is None:
            return None
        experiment.raw_requests = (
            [RawRequest.model_validate(raw_request) for raw_request in experiment.raw_requests]
            if experiment.raw_requests
            else None
        )
        return get_experiment_cls_from_provider(experiment.provider).model_validate(experiment)

    @staticmethod
    def create_experiment(
        experiment_id: str,
        model: str,
        name: str,
        processed_file_path: str,
        api_key: str | None = None,
        description: str | None = None,
        provider: str = "openai",
        endpoint: str = "/v1/chat/completions",
        raw_requests: list[RawRequest] | None = None,
        response_format: BaseModel | dict | None = None,
        results_file_path: str = "results.jsonl",
    ) -> Experiment:
        if ExperimentManager.retrieve(experiment_id=experiment_id) is not None:
            raise ValueError(f"Experiment with id: {experiment_id} already exists")
        if isinstance(response_format, BaseModel):
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "schema": response_format.model_json_schema(),
                    "name": response_format.__class__.__name__,
                    "strict": True,
                },
            }
        api_key = api_key or get_default_api_key_from_provider(provider)
        if not api_key:
            raise ValueError(
                f"No API key found in environment variables for provider: {provider}. Either set the API key in the environment variables or provide it through the api_key parameter."
            )
        experiment = get_experiment_cls_from_provider(provider).model_validate(
            {
                "id": experiment_id,
                "model": model,
                "name": name,
                "description": description,
                "provider": provider,
                "endpoint": endpoint,
                "api_key": api_key,
                "raw_requests": raw_requests,
                "response_format": response_format,
                "processed_file_path": processed_file_path,
                "results_file_path": results_file_path,
            }
        )
        if not os.path.exists(processed_file_path):
            experiment.write_processed_batch_file()
        experiment.save()
        return experiment

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
