"""Tests for base MongoEngine class."""

import copy

import mongoengine
import pytest
from flask import Flask

import flask_mongoengine2
from flask_mongoengine2 import MongoEngine, current_mongoengine_instance, documents
from flask_mongoengine2.connection import FLAT_CONFIG_DEPRECATION_MESSAGE


def _settings(db_name, alias="default"):
    return {"MONGODB_SETTINGS": {"db": db_name, "alias": alias}}


def test_mongoengine_class__should_raise_type_error__if_config_not_dict():
    """MongoEngine will handle None values, but will pass anything else as app."""
    input_value = "Not dict type"
    with pytest.raises(TypeError) as error:
        MongoEngine(input_value)
    assert str(error.value) == "Invalid Flask application instance"


@pytest.mark.parametrize("input_value", [None, "Not dict type"])
def test_init_app__should_raise_type_error__if_config_not_dict(input_value):
    db = MongoEngine()
    with pytest.raises(TypeError) as error:
        db.init_app(input_value)
    assert str(error.value) == "Invalid Flask application instance"


def test_init_app__should_raise__if_already_initialized(app):
    app.config.update(_settings("flask_mongoengine_test_db"))
    db = MongoEngine(app)
    with pytest.raises(ValueError, match="Extension already initialized"):
        db.init_app(app)


def test_init_app__should_use_each_app_config__for_several_apps(app):
    """Regression: app.config of the first app was reused for the next apps."""
    db = MongoEngine()
    app.config.update(_settings("flask_mongoengine_test_db_1", alias="first"))
    db.init_app(app)

    other_app = Flask("other")
    other_app.config.update(_settings("flask_mongoengine_test_db_2", alias="second"))
    db.init_app(other_app)

    assert list(app.extensions["mongoengine"][db]["conn"]) == ["first"]
    assert list(other_app.extensions["mongoengine"][db]["conn"]) == ["second"]
    assert db.app is other_app


def test_passing_config__should_warn_once_and_take_priority(app):
    app.config.update(_settings("should_not_be_used"))
    config = _settings("flask_mongoengine_test_db", alias="from_config")
    with pytest.warns(DeprecationWarning, match="flat configuration") as record:
        db = MongoEngine(app, config=config)

    assert len(record) == 1
    assert str(record[0].message) == FLAT_CONFIG_DEPRECATION_MESSAGE
    assert list(db.connection) == ["from_config"]


def test_passing_config_without_app__should_warn():
    with pytest.warns(DeprecationWarning, match="flat configuration"):
        MongoEngine(config={"MONGODB_SETTINGS": {}})


def test_current_mongoengine_instance__return_none__without_extension(app):
    assert current_mongoengine_instance() is None


def test_document_classes__are_extended_versions():
    db = MongoEngine()
    assert db.Document is documents.Document
    assert db.DynamicDocument is documents.DynamicDocument
    assert db.EmbeddedDocument is documents.EmbeddedDocument
    assert db.DynamicEmbeddedDocument is documents.DynamicEmbeddedDocument


@pytest.mark.parametrize(
    "name",
    ["StringField", "ListField", "ReferenceField", "connect", "ValidationError"],
)
def test_getattr__should_proxy_mongoengine_module(name):
    assert getattr(MongoEngine(), name) is getattr(mongoengine, name)


def test_getattr__should_raise_attribute_error__for_unknown_name():
    with pytest.raises(AttributeError, match="'MongoEngine' object has no attribute"):
        MongoEngine().NotExistingField  # noqa: B018


def test_getattr__should_not_proxy_dunder_names():
    db = MongoEngine()
    assert not hasattr(db, "__file__")
    assert not hasattr(db, "__path__")
    # Copy protocol must not be confused by module attributes.
    assert isinstance(copy.copy(db), MongoEngine)


def test_version__is_exposed():
    assert isinstance(flask_mongoengine2.__version__, str)
