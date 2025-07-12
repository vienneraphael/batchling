from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from batchling.db.models import Experiment


def create_experiment(
    db: Session,
    id: str,
    model: str,
    name: str | None = None,
    description: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    template_messages: list[dict] | None = None,
    placeholders: list[dict] | None = None,
    response_format: dict | None = None,
    input_file_path: str | None = None,
    input_file_id: str | None = None,
    status_value: str = "created",
    batch_id: str | None = None,
) -> Experiment:
    """Create an experiment

    Parameters
    ----------
    db : Session
        The database session
    id : str
        The id of the experiment
    name : str
        The name of the experiment
    description : str
        The description of the experiment
    model : str
        The model to use for the experiment
    base_url : str
        The base url of the experiment
    api_key : str
        The api key of the experiment
    template_messages : list[dict]
        The template messages of the experiment
    placeholders : list[dict]
        The placeholders of the experiment
    response_format : dict
        The response format of the experiment
    input_file_path : str
        The path to the input file
    input_file_id : str
        The id of the input file
    status_value : str
        The status of the experiment
    batch_id : str
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
        base_url=base_url,
        api_key=api_key,
        template_messages=template_messages,
        placeholders=placeholders,
        response_format=response_format,
        input_file_path=input_file_path,
        input_file_id=input_file_id,
        status_value=status_value,
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
    db: Session, limit: int | None = None, offset: int | None = None
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

    Returns
    -------
    list[Experiment]
        The list of experiments
    """
    stmt = select(Experiment).limit(limit).offset(offset)
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
