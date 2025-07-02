from sqlalchemy.orm import Session

from batchling.db.models import Experiment


def create_experiment(
    db: Session,
    name: str,
    description: str,
    model: str,
    response_format: dict,
    input_file_path: str,
    input_file_id: str,
    status: str,
    batch_id: str,
) -> Experiment:
    """Create an experiment

    Parameters
    ----------
    db : Session
        The database session
    name : str
        The name of the experiment
    description : str
        The description of the experiment
    model : str
        The model to use for the experiment
    response_format : dict
        The response format of the experiment
    input_file_path : str
        The path to the input file
    input_file_id : str
        The id of the input file
    status : str
        The status of the experiment
    batch_id : str
        The id of the batch

    Returns
    -------
    Experiment
        The created experiment
    """
    experiment = Experiment(
        name=name,
        description=description,
        model=model,
        response_format=response_format,
        input_file_path=input_file_path,
        input_file_id=input_file_id,
        status=status,
        batch_id=batch_id,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


def get_experiment(db: Session, experiment_id: int) -> Experiment:
    """Get an experiment

    Parameters
    ----------
    db : Session
        The database session
    experiment_id : int
        The id of the experiment

    Returns
    -------
    Experiment
        The experiment
    """
    return db.query(Experiment).filter(Experiment.id == experiment_id).first()
