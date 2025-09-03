from datetime import datetime

import pytest

from batchling.api_utils import get_default_api_key_from_provider
from batchling.db.crud import (
    create_experiment,
    delete_experiment,
    get_experiment,
    get_experiments,
    update_experiment,
)
from batchling.db.session import destroy_db, get_db, init_db


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
        id="experiment-test-1",
        model="gpt-4o-mini",
        name="test 1",
        description="test experiment number 1",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    assert experiment is not None
    assert experiment.model == "gpt-4o-mini"
    assert experiment.id == "experiment-test-1"
    assert experiment.name == "test 1"
    assert experiment.description == "test experiment number 1"
    assert experiment.created_at is not None
    assert experiment.updated_at is not None
    assert experiment.updated_at == experiment.created_at


def test_get_experiment(db):
    now = datetime.now()
    create_experiment(
        db=db,
        id="experiment-test-2",
        model="gpt-4o-mini",
        name="test 2",
        description="test experiment number 2",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    experiment = get_experiment(db=db, id="experiment-test-2")
    assert experiment is not None
    assert experiment.model == "gpt-4o-mini"
    assert experiment.id == "experiment-test-2"
    assert experiment.name == "test 2"
    assert experiment.description == "test experiment number 2"
    assert experiment.api_key == "test-key"


def test_update_experiment(db):
    now = datetime.now()
    experiment = create_experiment(
        db=db,
        id="experiment-test-3",
        model="gpt-4o-mini",
        name="test 3",
        description="test experiment number 3",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    update_dict = {"name": "test 3 updated", "description": "test experiment number 3 updated"}
    updated_experiment = update_experiment(db=db, id="experiment-test-3", **update_dict)
    assert updated_experiment is not None
    assert updated_experiment.model == "gpt-4o-mini"
    assert updated_experiment.id == "experiment-test-3"
    assert updated_experiment.name == update_dict["name"]
    assert updated_experiment.description == update_dict["description"]
    assert updated_experiment.updated_at is not None
    assert updated_experiment.updated_at > experiment.created_at


def test_delete_experiment(db):
    now = datetime.now()
    create_experiment(
        db=db,
        id="experiment-test-4",
        model="gpt-4o-mini",
        name="test 4",
        description="test experiment number 4",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    delete_experiment(db=db, id="experiment-test-4")
    assert get_experiment(db=db, id="experiment-test-4") is None


def test_get_experiments(db):
    now = datetime.now()
    create_experiment(
        db=db,
        id="experiment-test-5",
        model="gpt-4o-mini",
        name="test 5",
        description="test experiment number 5",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=now,
        updated_at=now,
    )
    after = datetime.now()
    create_experiment(
        db=db,
        id="experiment-test-6",
        model="gpt-4o-mini",
        name="test 6",
        description="test experiment number 6",
        api_key=get_default_api_key_from_provider(provider="openai"),
        created_at=after,
        updated_at=after,
    )
    experiments = get_experiments(db=db)
    assert len(experiments) == 2
    assert experiments[0].id == "experiment-test-6"
    assert experiments[1].id == "experiment-test-5"
