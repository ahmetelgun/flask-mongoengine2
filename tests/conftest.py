import os
from collections.abc import Iterator
from datetime import datetime, timezone

import mongoengine
import pytest
from flask import Flask
from pymongo import MongoClient

from flask_mongoengine2 import MongoEngine

MONGO_HOST = os.environ.get("MONGO_TEST_HOST", "localhost")
MONGO_PORT = int(os.environ.get("MONGO_TEST_PORT", "27017"))
TEST_DATABASES = (
    "flask_mongoengine_test_db",
    "flask_mongoengine_test_db_1",
    "flask_mongoengine_test_db_2",
    "flask_mongoengine_list_test_db",
)


@pytest.fixture(autouse=True, scope="session")
def session_clean_up() -> Iterator[None]:
    """Mandatory tests environment clean up before/after test session."""
    client = MongoClient(MONGO_HOST, MONGO_PORT)
    for name in TEST_DATABASES:
        client.drop_database(name)

    yield

    for name in TEST_DATABASES:
        client.drop_database(name)
    client.close()


@pytest.fixture()
def app() -> Iterator[Flask]:
    app = Flask(__name__)
    app.config["TESTING"] = True

    with app.app_context():
        yield app

    mongoengine.connection.disconnect_all()


@pytest.fixture()
def db(app) -> Iterator[MongoEngine]:
    app.config["MONGODB_SETTINGS"] = [
        {
            "db": "flask_mongoengine_test_db",
            "host": MONGO_HOST,
            "port": MONGO_PORT,
            "alias": "default",
        }
    ]
    test_db = MongoEngine(app)
    db_name = (
        test_db.connection["default"].get_database("flask_mongoengine_test_db").name
    )

    if not db_name.endswith("_test_db"):
        raise RuntimeError(
            f"DATABASE_URL must point to testing db, not to master db ({db_name})"
        )

    # Clear database before tests, for cases when some test failed before.
    test_db.connection["default"].drop_database(db_name)

    yield test_db

    # Clear database after tests, for graceful exit.
    test_db.connection["default"].drop_database(db_name)


@pytest.fixture()
def todo(db):
    class Todo(db.Document):
        title = mongoengine.StringField(max_length=60)
        text = mongoengine.StringField()
        done = mongoengine.BooleanField(default=False)
        pub_date = mongoengine.DateTimeField(default=lambda: datetime.now(timezone.utc))
        comments = mongoengine.ListField(mongoengine.StringField())
        comment_count = mongoengine.IntField()

    return Todo
