import os
from datetime import datetime

from dotenv import load_dotenv
from pydantic import BaseModel

from batchling.db.crud import create_experiment, delete_experiment, update_experiment
from batchling.db.session import get_db, init_db
from batchling.experiment import Experiment
from batchling.request import RawRequest, raw_request_list_adapter
from batchling.utils.api import get_default_api_key_from_provider
from batchling.utils.classes import get_experiment_cls_from_provider


class ExperimentManager(BaseModel):
    def model_post_init(self, context):
        load_dotenv(override=True)
        init_db()

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
            experiment.raw_requests = raw_request_list_adapter.validate_python(
                experiment.raw_requests
            )
        return [
            get_experiment_cls_from_provider(experiment.provider).model_validate(experiment)
            for experiment in experiments
        ]

    @staticmethod
    def retrieve(experiment_name: str) -> Experiment | None:
        from batchling.db.crud import get_experiment

        with get_db() as db:
            experiment = get_experiment(db=db, name=experiment_name)
        if experiment is None:
            return None
        experiment.raw_requests = raw_request_list_adapter.validate_python(experiment.raw_requests)
        return get_experiment_cls_from_provider(experiment.provider).model_validate(experiment)

    @staticmethod
    def save_experiment(experiment: Experiment) -> None:
        if experiment.batch_id is not None:
            raise ValueError("Can only save an experiment in created status.")
        with get_db() as db:
            create_experiment(
                db=db,
                name=experiment.name,
                model=experiment.model,
                api_key=experiment.api_key,
                uid=experiment.uid,
                title=experiment.title,
                description=experiment.description,
                provider=experiment.provider,
                endpoint=experiment.endpoint,
                raw_requests=experiment.raw_requests,
                response_format=experiment.response_format,
                processed_file_path=experiment.processed_file_path,
                results_file_path=experiment.results_file_path,
                created_at=experiment.created_at,
                updated_at=experiment.updated_at,
            )

    @staticmethod
    def create_experiment(
        experiment_name: str,
        model: str,
        processed_file_path: str,
        title: str | None = None,
        api_key: str | None = None,
        description: str | None = None,
        provider: str = "openai",
        endpoint: str = "/v1/chat/completions",
        raw_requests: list[RawRequest] | None = None,
        response_format: BaseModel | dict | None = None,
        results_file_path: str = "results.jsonl",
    ) -> Experiment:
        now = datetime.now()
        if ExperimentManager.retrieve(experiment_name=experiment_name) is not None:
            new_experiment_name = f"{provider}_{model}_{now.strftime('%Y%m%d_%H%M%S')}"
            message = (
                f"Experiment name '{experiment_name}' already exists.\n"
                f"Using custom name: {new_experiment_name}\n"
                "Feel free to rename the experiment later.\n"
            )
            print(message)
            experiment_name = new_experiment_name
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
        experiment = get_experiment_cls_from_provider(provider).model_validate(
            {
                "name": experiment_name,
                "model": model,
                "title": title,
                "description": description,
                "provider": provider,
                "endpoint": endpoint,
                "api_key": api_key,
                "raw_requests": raw_requests,
                "response_format": response_format,
                "processed_file_path": processed_file_path,
                "results_file_path": results_file_path,
                "created_at": now,
                "updated_at": now,
            }
        )
        if not os.path.exists(processed_file_path):
            experiment.write_processed_batch_file()
        ExperimentManager.save_experiment(experiment)
        return experiment

    @staticmethod
    def start_experiment(experiment_name: str) -> Experiment:
        experiment = ExperimentManager.retrieve(experiment_name=experiment_name)
        if experiment is None:
            raise ValueError(f"Experiment with name: {experiment_name} not found")
        if experiment.batch_id is not None:
            raise ValueError(f"Experiment with name: {experiment_name} was already started")
        experiment.start()
        with get_db() as db:
            update_experiment(
                db=db,
                name=experiment.name,
                **{
                    "updated_at": datetime.now(),
                    "batch_id": experiment.batch_id,
                    "provider_file_id": experiment.provider_file_id,
                },
            )
        return experiment

    @staticmethod
    def get_results(experiment_name: str) -> list[dict]:
        experiment = ExperimentManager.retrieve(experiment_name=experiment_name)
        if experiment is None:
            raise ValueError(f"Experiment with name: {experiment_name} not found")
        return experiment.get_results()

    @staticmethod
    def update_experiment(experiment_name: str, **kwargs) -> Experiment:
        experiment = ExperimentManager.retrieve(experiment_name=experiment_name)
        if experiment is None:
            raise ValueError(f"Experiment with name: {experiment_name} not found")
        if experiment.batch_id is not None:
            raise ValueError("Cannot update an experiment that has already been started.")
        if "name" in kwargs:
            if ExperimentManager.retrieve(experiment_name=kwargs["name"]) is not None:
                raise ValueError(
                    "name cannot be updated, because an experiment with this name already exists"
                )
        kwargs["updated_at"] = datetime.now()
        experiment = experiment.update(**kwargs)
        with get_db() as db:
            update_experiment(db=db, name=experiment.name, **kwargs)
        return experiment

    @staticmethod
    def delete_experiment(experiment_name: str) -> None:
        experiment = ExperimentManager.retrieve(experiment_name=experiment_name)
        if experiment is None:
            raise ValueError(f"Experiment with name: {experiment_name} not found")
        with get_db() as db:
            delete_experiment(db=db, name=experiment.name)
        experiment.delete()

    @staticmethod
    def cancel_experiment(experiment_name: str) -> None:
        experiment = ExperimentManager.retrieve(experiment_name=experiment_name)
        if experiment is None:
            raise ValueError(f"Experiment with name: {experiment_name} not found")
        experiment.cancel()
        with get_db() as db:
            update_experiment(db=db, name=experiment.name, updated_at=datetime.now())
