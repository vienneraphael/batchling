import typing as t
from datetime import datetime

from batchling.db.models import Experiment
from batchling.request import processed_request_list_adapter, raw_request_list_adapter

if t.TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from batchling.request import ProcessedRequest, RawRequest


def create_experiment(
    db: "Session",
    name: str,
    model: str,
    api_key: str,
    created_at: datetime,
    updated_at: datetime,
    uid: str,
    title: str | None = None,
    description: str | None = None,
    provider: str = "openai",
    endpoint: str = "/v1/chat/completions",
    raw_requests: list["RawRequest"] | None = None,
    processed_requests: list["ProcessedRequest"] | None = None,
    response_format: dict | None = None,
    processed_file_path: str | None = None,
    results_file_path: str = "results.jsonl",
    provider_file_id: str | None = None,
    batch_id: str | None = None,
) -> Experiment:
    """Create an experiment

    Parameters
    ----------
    db : Session
        The database session
    name : str
        The name of the experiment
    model : str
        The model to use for the experiment
    api_key : str
        The api key of the experiment
    created_at : datetime
        Creation time of the experiment
    updated_at : datetime
        Last update time of the experiment
    uid : str
        The unique identifier of the experiment
    title : str | None
        The title of the experiment
    description : str | None
        The description of the experiment
    provider : str
        The provider of the experiment
    endpoint : str
        The generation endpoint of the experiment, e.g. /v1/chat/completions, /v1/embeddings..
    raw_requests : list[RawRequest] | None
        The raw requests of the experiment
    processed_requests : list[ProcessedRequest] | None
        The processed requests of the experiment
    response_format : dict | None
        The response format of the experiment
    processed_file_path : str | None
        The path to the processed file
    results_file_path : str
        The path to the results file
    provider_file_id : str | None
        The id of the provider file
    batch_id : str | None
        The id of the batch
    Returns
    -------
    Experiment
        The created experiment
    """
    raw_requests = raw_request_list_adapter.dump_python(raw_requests) if raw_requests else None
    processed_requests = (
        processed_request_list_adapter.dump_python(processed_requests)
        if processed_requests
        else None
    )
    experiment = Experiment(
        name=name,
        uid=uid,
        title=title,
        description=description,
        created_at=created_at,
        updated_at=updated_at,
        model=model,
        provider=provider,
        endpoint=endpoint,
        api_key=api_key,
        raw_requests=raw_requests,
        processed_requests=processed_requests,
        response_format=response_format,
        processed_file_path=processed_file_path,
        results_file_path=results_file_path,
        provider_file_id=provider_file_id,
        batch_id=batch_id,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def get_experiment(db: "Session", name: str) -> Experiment | None:
    """Get an experiment

    Parameters
    ----------
    db : Session
        The database session
    name : str
        The name of the experiment

    Returns
    -------
    Experiment
        The experiment
    """
    from sqlalchemy import select

    stmt = select(Experiment).where(Experiment.name == name)
    return db.execute(stmt).scalar_one_or_none()


def get_experiments(
    db: "Session",
    limit: int | None = None,
    offset: int | None = None,
    order_by: str | None = "updated_at",
    ascending: bool = False,
    filter_by: str | None = "id",
    filter_value: str | None = None,
    starts_with_field: str | None = None,
    starts_with: str | None = None,
) -> list[Experiment]:
    """Get all experiments

    Parameters
    ----------
    db : Session
        The database session
    limit : int
        The limit of the experiments
    offset : int
        The offset of the experiments
    order_by : str | None
        The field to order by
    ascending : bool
        Whether to order in ascending order (default is descending)
    filter_by : str | None
        The field to filter by
    filter_value : str | None
        The value to filter by
    starts_with_field : str | None
        The field to filter by starts with
    starts_with : str | None
        The value to filter by starts with
    Returns
    -------
    list[Experiment]
        The list of experiments
    """
    from sqlalchemy import asc, desc, select

    direction = asc if ascending else desc
    stmt = select(Experiment)
    if filter_by is not None and filter_value is not None:
        stmt = stmt.where(getattr(Experiment, filter_by) == filter_value)
    if starts_with_field is not None and starts_with is not None:
        stmt = stmt.where(getattr(Experiment, starts_with_field).istartswith(starts_with))
    stmt = stmt.order_by(direction(order_by))
    if limit is not None:
        stmt = stmt.limit(limit)
    if offset is not None:
        stmt = stmt.offset(offset)
    return db.execute(stmt).scalars().all()


def update_experiment(
    db: "Session",
    name: str,
    **kwargs: dict,
) -> Experiment | None:
    """Update an experiment

    Parameters
    ----------
    db : Session
        The database session
    name : str
        The name of the experiment
    **kwargs : dict
        The fields to update

    Returns
    -------
    Experiment
        The updated experiment
    """
    from sqlalchemy import update

    kwargs["updated_at"] = datetime.now()
    stmt = update(Experiment).where(Experiment.name == name).values(**kwargs)
    db.execute(stmt)
    db.commit()
    return get_experiment(db=db, name=name)


def delete_experiment(db: "Session", name: str) -> bool:
    """Delete an experiment

    Parameters
    ----------
    db : Session
        The database session
    name : str
        The name of the experiment
    """
    from sqlalchemy import delete

    stmt = delete(Experiment).where(Experiment.name == name)
    db.execute(stmt)
    db.commit()
    return True
