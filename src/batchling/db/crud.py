from datetime import datetime

from sqlalchemy import asc, delete, desc, select, update
from sqlalchemy.orm import Session

from batchling.db.models import Experiment


def create_experiment(
    db: Session,
    id: str,
    model: str,
    api_key_name: str = "OPENAI_API_KEY",
    name: str | None = None,
    description: str | None = None,
    provider: str = "openai",
    endpoint: str = "/v1/chat/completions",
    template_messages: list[dict] | None = None,
    placeholders: list[dict] | None = None,
    response_format: dict | None = None,
    max_tokens_per_request: int | None = None,
    input_file_path: str | None = None,
    output_file_path: str = "results.jsonl",
    input_file_id: str | None = None,
    is_setup: bool = False,
    batch_id: str | None = None,
) -> Experiment:
    """Create an experiment

    Parameters
    ----------
    db : Session
        The database session
    id : str
        The id of the experiment
    model : str
        The model to use for the experiment
    api_key_name : str
        The api key name of the experiment
    name : str | None
        The name of the experiment
    description : str | None
        The description of the experiment
    provider : str
        The provider of the experiment
    endpoint : str
        The endpoint of the experiment
    template_messages : list[dict] | None
        The template messages of the experiment
    placeholders : list[dict]
        The placeholders of the experiment
    response_format : dict | None
        The response format of the experiment
    max_tokens_per_request : int
        The max tokens per request of the experiment
    input_file_path : str | None
        The path to the input file
    output_file_path : str
        The path to the output file
    input_file_id : str | None
        The id of the input file
    is_setup : bool
        Whether the experiment is setup
    batch_id : str | None
        The id of the batch
    Returns
    -------
    Experiment
        The created experiment
    """
    now = datetime.now()
    experiment = Experiment(
        id=id,
        name=name,
        description=description,
        created_at=now,
        updated_at=now,
        model=model,
        provider=provider,
        endpoint=endpoint,
        api_key_name=api_key_name,
        template_messages=template_messages,
        placeholders=placeholders,
        response_format=response_format,
        max_tokens_per_request=max_tokens_per_request,
        input_file_path=input_file_path,
        output_file_path=output_file_path,
        input_file_id=input_file_id,
        is_setup=is_setup,
        batch_id=batch_id,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def get_experiment(db: Session, id: str) -> Experiment | None:
    """Get an experiment

    Parameters
    ----------
    db : Session
        The database session
    id : str
        The id of the experiment

    Returns
    -------
    Experiment
        The experiment
    """
    stmt = select(Experiment).where(Experiment.id == id)
    return db.execute(stmt).scalar_one_or_none()


def get_experiments(
    db: Session,
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
    db: Session,
    id: str,
    **kwargs: dict,
) -> Experiment | None:
    """Update an experiment

    Parameters
    ----------
    db : Session
        The database session
    id : str
        The id of the experiment
    **kwargs : dict
        The fields to update

    Returns
    -------
    Experiment
        The updated experiment
    """
    kwargs["updated_at"] = datetime.now()
    stmt = update(Experiment).where(Experiment.id == id).values(**kwargs)
    db.execute(stmt)
    db.commit()
    return get_experiment(db=db, id=id)


def delete_experiment(db: Session, id: str) -> bool:
    """Delete an experiment

    Parameters
    ----------
    db : Session
        The database session
    id : str
        The id of the experiment
    """
    stmt = delete(Experiment).where(Experiment.id == id)
    db.execute(stmt)
    db.commit()
    return True
