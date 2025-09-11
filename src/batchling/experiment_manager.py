import os
from datetime import datetime

from dotenv import load_dotenv
from pydantic import BaseModel

from batchling.db.crud import create_experiment, delete_experiment, update_experiment
from batchling.db.session import get_db, init_db
from batchling.experiment import Experiment
from batchling.request import RawRequest
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
    def save_experiment(experiment: Experiment) -> None:
        if experiment.batch_id is not None:
            raise ValueError("Can only save an experiment in created status.")
        now = datetime.now()
        with get_db() as db:
            create_experiment(
                db=db,
                id=experiment.id,
                model=experiment.model,
                api_key=experiment.api_key,
                name=experiment.name,
                description=experiment.description,
                provider=experiment.provider,
                endpoint=experiment.endpoint,
                raw_requests=experiment.raw_requests,
                response_format=experiment.response_format,
                processed_file_path=experiment.processed_file_path,
                results_file_path=experiment.results_file_path,
                created_at=now,
                updated_at=now,
            )

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
        ExperimentManager.save_experiment(experiment)
        return experiment

    @staticmethod
    def start_experiment(experiment_id: str) -> Experiment:
        experiment = ExperimentManager.retrieve(experiment_id=experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        if experiment.batch_id is not None:
            raise ValueError(f"Experiment with id: {experiment_id} was already started")
        experiment.start()
        with get_db() as db:
            update_experiment(
                db=db,
                id=experiment.id,
                kwargs={
                    "updated_at": datetime.now(),
                    "batch_id": experiment.batch_id,
                    "provider_file_id": experiment.provider_file_id,
                },
            )
        return experiment

    @staticmethod
    def get_results(experiment_id: str) -> list[dict]:
        experiment = ExperimentManager.retrieve(experiment_id=experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        return experiment.get_results()

    @staticmethod
    def update_experiment(experiment_id: str, **kwargs) -> Experiment:
        experiment = ExperimentManager.retrieve(experiment_id=experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        if experiment.batch_id is not None:
            raise ValueError("Cannot update an experiment that has already been started.")
        if "id" in kwargs:
            raise ValueError(
                "id cannot be updated, please delete the experiment and create a new one"
            )
        kwargs["updated_at"] = datetime.now()
        experiment = experiment.update(**kwargs)
        with get_db() as db:
            update_experiment(db=db, id=experiment.id, **kwargs)
        return experiment

    @staticmethod
    def delete_experiment(experiment_id: str) -> None:
        experiment = ExperimentManager.retrieve(experiment_id=experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        with get_db() as db:
            delete_experiment(db=db, id=experiment.id)
        experiment.delete()

    @staticmethod
    def cancel_experiment(experiment_id: str) -> None:
        experiment = ExperimentManager.retrieve(experiment_id=experiment_id)
        if experiment is None:
            raise ValueError(f"Experiment with id: {experiment_id} not found")
        experiment.cancel()
        with get_db() as db:
            update_experiment(db=db, id=experiment.id, updated_at=datetime.now())
