"""Flask extension that provides integration with MongoEngine."""

from __future__ import annotations

from typing import Any

import mongoengine
from flask import Flask, current_app
from pymongo import MongoClient

from flask_mongoengine2 import documents
from flask_mongoengine2.connection import (
    _warn_flat_config,
    create_connections,
    get_connection_settings,
)
from flask_mongoengine2.pagination import ListFieldPagination, Pagination
from flask_mongoengine2.sessions import MongoEngineSession, MongoEngineSessionInterface

try:
    from flask_mongoengine2._version import version as __version__
except ImportError:  # pragma: no cover - not installed via setuptools-scm
    __version__ = "0.0.0"

__all__ = (
    "ListFieldPagination",
    "MongoEngine",
    "MongoEngineSession",
    "MongoEngineSessionInterface",
    "Pagination",
    "__version__",
    "create_connections",
    "current_mongoengine_instance",
    "get_connection_settings",
)


def current_mongoengine_instance() -> MongoEngine | None:
    """Return a MongoEngine instance associated with current Flask app."""
    instances = current_app.extensions.get("mongoengine", {})
    return next((k for k in instances if isinstance(k, MongoEngine)), None)


class MongoEngine:
    """Main class used for initialization of Flask-MongoEngine2.

    Any attribute not defined here (fields, ``connect``, errors, ...) is proxied
    to the :mod:`mongoengine` module, so ``db.StringField`` is
    :class:`mongoengine.fields.StringField`.
    """

    # Extended documents classes
    Document = documents.Document
    DynamicDocument = documents.DynamicDocument
    EmbeddedDocument = documents.EmbeddedDocument
    DynamicEmbeddedDocument = documents.DynamicEmbeddedDocument

    def __init__(self, app: Flask | None = None, config: dict | None = None):
        self.app: Flask | None = None
        self.config = config

        if app is not None:
            self.init_app(app, config)
        elif config is not None:
            _warn_flat_config(stacklevel=2)

    def init_app(self, app: Flask, config: dict | None = None) -> None:
        if not isinstance(app, Flask):
            raise TypeError("Invalid Flask application instance")

        if config is not None:
            _warn_flat_config(stacklevel=2)
            # Passed config has max priority over init config.
            self.config = config

        extensions = app.extensions.setdefault("mongoengine", {})
        if self in extensions:
            # Raise an exception if extension already initialized as
            # potentially new configuration would not be loaded.
            raise ValueError("Extension already initialized")

        # If no configs passed, use app.config.
        connections = create_connections(self.config or app.config)

        self.app = app
        # Store objects in application instance so that multiple apps do not
        # end up accessing the same objects.
        extensions[self] = {"app": app, "conn": connections}

    @property
    def connection(self) -> dict[str, MongoClient]:
        """
        Return MongoDB connection(s) associated with this MongoEngine
        instance.
        """
        return current_app.extensions["mongoengine"][self]["conn"]

    def __getattr__(self, attr_name: str) -> Any:
        """
        Mongoengine backward compatibility handler.

        Provide original :mod:`mongoengine` module methods/classes if they are not
        modified by us, and not mapped directly.
        """
        if attr_name.startswith("__") and attr_name.endswith("__"):
            raise AttributeError(attr_name)
        try:
            return getattr(mongoengine, attr_name)
        except AttributeError:
            raise AttributeError(
                f"{type(self).__name__!r} object has no attribute {attr_name!r}"
            ) from None
