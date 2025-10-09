import uuid
from datetime import datetime

import pytest

from batchling.db.crud import (
    create_experiment,
    delete_experiment,
    get_experiment,
    get_experiments,
    update_experiment,
)
from batchling.db.session import destroy_db, get_db, init_db
from batchling.utils.api import get_default_api_key_from_provider


@pytest.fixture
def db():
    init_db()
    with get_db() as session:
        yield session
    destroy_db()


def test_create_experiment(db):
    now = datetime.now()
    experiment = create_experiment(
        db=db,
        name="experiment-test-1",
        model="gpt-4o-mini",
        uid=str(uuid.uuid4()),
        title="test 1",
        description="test experiment number 1",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    assert experiment is not None
    assert experiment.model == "gpt-4o-mini"
    assert experiment.name == "experiment-test-1"
    assert experiment.uid is not None
    assert len(experiment.uid) == 36  # UUID4 string length
    assert experiment.title == "test 1"
    assert experiment.description == "test experiment number 1"
    assert experiment.created_at is not None
    assert experiment.updated_at is not None
    assert experiment.updated_at == experiment.created_at


def test_get_experiment(db):
    now = datetime.now()
    create_experiment(
        db=db,
        name="experiment-test-2",
        model="gpt-4o-mini",
        uid=str(uuid.uuid4()),
        title="test 2",
        description="test experiment number 2",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    experiment = get_experiment(db=db, name="experiment-test-2")
    assert experiment is not None
    assert experiment.model == "gpt-4o-mini"
    assert experiment.name == "experiment-test-2"
    assert experiment.title == "test 2"
    assert experiment.description == "test experiment number 2"
    assert experiment.api_key == "test-key"


def test_update_experiment(db):
    now = datetime.now()
    experiment = create_experiment(
        db=db,
        name="experiment-test-3",
        model="gpt-4o-mini",
        uid=str(uuid.uuid4()),
        title="test 3",
        description="test experiment number 3",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    update_dict = {
        "title": "test 3 updated",
        "description": "test experiment number 3 updated",
    }
    updated_experiment = update_experiment(db=db, name="experiment-test-3", **update_dict)
    assert updated_experiment is not None
    assert updated_experiment.model == "gpt-4o-mini"
    assert updated_experiment.name == "experiment-test-3"
    assert updated_experiment.title == update_dict["title"]
    assert updated_experiment.description == update_dict["description"]
    assert updated_experiment.updated_at is not None
    assert updated_experiment.updated_at > experiment.created_at


def test_delete_experiment(db):
    now = datetime.now()
    create_experiment(
        db=db,
        name="experiment-test-4",
        model="gpt-4o-mini",
        uid=str(uuid.uuid4()),
        title="test 4",
        description="test experiment number 4",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    delete_experiment(db=db, name="experiment-test-4")
    assert get_experiment(db=db, name="experiment-test-4") is None


def test_get_experiments(db):
    now = datetime.now()
    create_experiment(
        db=db,
        name="experiment-test-5",
        model="gpt-4o-mini",
        uid=str(uuid.uuid4()),
        title="test 5",
        description="test experiment number 5",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    after = datetime.now()
    create_experiment(
        db=db,
        name="experiment-test-6",
        model="gpt-4o-mini",
        uid=str(uuid.uuid4()),
        title="test 6",
        description="test experiment number 6",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=after,
        updated_at=after,
    )
    experiments = get_experiments(db=db)
    assert len(experiments) == 2
    assert experiments[0].name == "experiment-test-6"
    assert experiments[1].name == "experiment-test-5"
    # Verify that each experiment has a unique uid
    assert experiments[0].uid != experiments[1].uid
    assert len(experiments[0].uid) == 36
    assert len(experiments[1].uid) == 36
