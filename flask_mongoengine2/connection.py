"""Module responsible for connection setup."""

from __future__ import annotations

import warnings
from collections.abc import Mapping
from typing import Any

import mongoengine
from pymongo import MongoClient

__all__ = (
    "create_connections",
    "get_connection_settings",
)

FLAT_CONFIG_DEPRECATION_MESSAGE = (
    "Passing flat configuration is deprecated. Please check "
    "https://flask-mongoengine2.readthedocs.io/en/latest/flask_config.html "
    "for more info."
)

# pymongo settings are case-insensitive, but mongoengine matches some of them by
# exact (camelCase) name, overriding pymongo behaviour (issue #451). We map
# lower-cased names to the canonical pymongo spelling.
_KNOWN_CAMEL_CASE_SETTINGS = {
    name.lower(): name
    for name in (
        "directConnection",
        "maxPoolSize",
        "minPoolSize",
        "maxIdleTimeMS",
        "maxConnecting",
        "socketTimeoutMS",
        "connectTimeoutMS",
        "serverSelectionTimeoutMS",
        "waitQueueTimeoutMS",
        "heartbeatFrequencyMS",
        "retryWrites",
        "retryReads",
        "zlibCompressionLevel",
        "uuidRepresentation",
        "srvServiceName",
        "srvMaxHosts",
        "wTimeoutMS",
        "replicaSet",
        "readPreference",
        "readPreferenceTags",
        "maxStalenessSeconds",
        "authSource",
        "authMechanism",
        "authMechanismProperties",
        "tlsInsecure",
        "tlsAllowInvalidCertificates",
        "tlsAllowInvalidHostnames",
        "tlsCAFile",
        "tlsCertificateKeyFile",
        "tlsCRLFile",
        "tlsCertificateKeyFilePassword",
        "tlsDisableOCSPEndpointCheck",
        "readConcernLevel",
        "loadBalanced",
        "serverMonitoringMode",
        "timeoutMS",
        "appName",
    )
}


def _warn_flat_config(stacklevel: int = 3) -> None:
    warnings.warn(
        FLAT_CONFIG_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=stacklevel
    )


def _get_name(setting_name: str) -> str:
    """Return known pymongo setting name, or lower case name for unknown."""
    lowered = setting_name.lower()
    return _KNOWN_CAMEL_CASE_SETTINGS.get(lowered, lowered)


def _sanitize_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Remove ``MONGODB_`` prefix from keys and normalize names for mongoengine."""
    resolved = {}
    for key, value in settings.items():
        if key.lower().startswith("mongodb_"):
            key = key[len("mongodb_") :]
        resolved[_get_name(key)] = value
    return resolved


def get_connection_settings(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """
    Given a config dict, return a list of sanitized MongoDB connection settings
    that we can then use to establish connections. For new applications, settings
    should exist in a ``MONGODB_SETTINGS`` key, but for backward compatibility we
    also support several config keys prefixed by ``MONGODB_``, e.g. ``MONGODB_HOST``,
    ``MONGODB_PORT``, etc.
    """
    if "MONGODB_SETTINGS" not in config:
        # No "MONGODB_SETTINGS": sanitize the "MONGODB_" keys as single connection.
        _warn_flat_config()
        flat = {k: v for k, v in config.items() if k.lower().startswith("mongodb_")}
        return [_sanitize_settings(flat)]

    settings = config["MONGODB_SETTINGS"]

    # A list of settings dicts describes several connections.
    if isinstance(settings, (list, tuple)):
        return [_sanitize_settings(settings_dict) for settings_dict in settings]

    # Otherwise, it should be a single dict describing a single connection.
    return [_sanitize_settings(settings)]


def create_connections(config: Mapping[str, Any]) -> dict[str, MongoClient]:
    """
    Given Flask application's config dict, extract relevant config vars
    out of it and establish MongoEngine connection(s) based on them.
    """
    if not config or not isinstance(config, Mapping):
        raise TypeError(f"Config dictionary expected, but {type(config)} received.")

    connections = {}
    for connection_setting in get_connection_settings(config):
        alias = connection_setting.setdefault(
            "alias", mongoengine.DEFAULT_CONNECTION_NAME
        )
        connection_setting.setdefault("uuidRepresentation", "standard")
        connections[alias] = mongoengine.connect(**connection_setting)

    return connections
