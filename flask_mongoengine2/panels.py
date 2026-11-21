"""Debug panel views and logic and related mongoDb event listeners."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import bson
from flask import current_app
from flask_debugtoolbar.panels import DebugPanel
from jinja2 import ChoiceLoader, PackageLoader
from pymongo import monitoring

__all__ = ["MongoDebugPanel", "mongo_command_logger"]

logger = logging.getLogger("flask_mongoengine2")


@dataclass
class RawQueryEvent:
    # noinspection PyUnresolvedReferences
    """Responsible for parsing monitoring events to web panel interface.

    :param _event: Succeeded or Failed event object from pymongo monitoring.
    :param _start_event: Started event object from pymongo monitoring.
    :param _is_query_pass: Boolean status of db query reported by pymongo monitoring.
    """

    _event: monitoring.CommandSucceededEvent | monitoring.CommandFailedEvent
    _start_event: monitoring.CommandStartedEvent
    _is_query_pass: bool

    @property
    def time(self) -> float:
        """Query execution time in milliseconds."""
        return self._event.duration_micros * 0.001

    @property
    def size(self) -> float:
        """Server response size in KiB (BSON encoded)."""
        try:
            return len(bson.encode(self.server_response)) / 1024
        except Exception:  # pragma: no cover - defensive, response from server
            return 0.0

    @property
    def database(self) -> str:
        """Query database target."""
        return self._start_event.database_name

    @property
    def collection(self):
        """Query collection target."""
        return self.server_command.get(self.command_name)

    @property
    def command_name(self) -> str:
        """Query db level operation/command name."""
        return self._event.command_name

    @property
    def operation_id(self) -> int:
        """MongoDb operation_id of the original request."""
        return self._start_event.operation_id

    @property
    def server_command(self) -> dict:
        """Raw MongoDb command send to server."""
        return self._start_event.command

    @property
    def server_response(self) -> dict:
        """Raw MongoDb response received from server."""
        return self._event.reply if self._is_query_pass else self._event.failure

    @property
    def request_status(self) -> str:
        """Query execution status."""
        return "Succeed" if self._is_query_pass else "Failed"


class MongoCommandLogger(monitoring.CommandListener):
    """Receive point for :class:`~.pymongo.monitoring.CommandListener` events.

    Count and parse incoming events for display in debug panel.
    """

    def __init__(self):
        self.total_time: float = 0
        self.started_operations_count: int = 0
        self.succeeded_operations_count: int = 0
        self.failed_operations_count: int = 0
        self.queries: list[RawQueryEvent] = []
        self.started_events: dict = {}

    @staticmethod
    def _event_key(event) -> tuple:
        """Started and final events are paired by connection and request id.

        ``operation_id`` is shared by all commands of one bulk operation, so it can
        not be used to pair events.
        """
        return event.connection_id, event.request_id

    def append_raw_query(self, event, request_status: bool) -> None:
        """Pair final event with its start event and include it to final list."""
        self.total_time += event.duration_micros
        start_event = self.started_events.pop(self._event_key(event), None)
        if start_event is None:
            # Started before tracker reset (e.g. previous request), nothing to show.
            logger.debug("Received final event without started event: %s", event)
            return
        self.queries.append(RawQueryEvent(event, start_event, request_status))

    def failed(self, event) -> None:
        """Receives 'failed' events. Required to track database answer to request."""
        logger.debug("Received 'Failed' event from driver: %s", event)
        self.failed_operations_count += 1
        self.append_raw_query(event, False)

    def reset_tracker(self) -> None:
        """Resets all counters to default, keeping instance itself the same."""
        self.__init__()

    def started(self, event) -> None:
        """Receives 'started' events. Required to track original request context."""
        logger.debug("Received 'Started' event from driver: %s", event)
        self.started_operations_count += 1
        self.started_events[self._event_key(event)] = event

    def succeeded(self, event) -> None:
        """Receives 'succeeded' events. Required to track database answer to request."""
        logger.debug("Received 'Succeeded' event from driver: %s", event)
        self.succeeded_operations_count += 1
        self.append_raw_query(event, True)


mongo_command_logger = MongoCommandLogger()


def _maybe_patch_jinja_loader(jinja_env) -> None:
    """Extend jinja_env loader with flask_mongoengine2 templates folder."""
    package_loader = PackageLoader("flask_mongoengine2", "templates")
    if not isinstance(jinja_env.loader, ChoiceLoader):
        jinja_env.loader = ChoiceLoader([jinja_env.loader, package_loader])
    elif not any(
        isinstance(loader, PackageLoader)
        and loader.package_name == "flask_mongoengine2"
        for loader in jinja_env.loader.loaders
    ):
        jinja_env.loader.loaders = [*jinja_env.loader.loaders, package_loader]


class MongoDebugPanel(DebugPanel):
    """Panel that shows information about MongoDB operations."""

    config_error_message = (
        "Pymongo monitoring configuration error. mongo_command_logger should be "
        "registered before database connection."
    )
    name = "MongoDB"
    has_content = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _maybe_patch_jinja_loader(self.jinja_env)

    @property
    def _context(self) -> dict:
        """Context for rendering, as property for easy testing."""
        return {
            "queries": mongo_command_logger.queries,
            "slow_query_limit": current_app.config.get(
                "MONGO_DEBUG_PANEL_SLOW_QUERY_LIMIT", 100
            ),
        }

    @property
    def is_properly_configured(self) -> bool:
        """Checks that all required watchers registered before Flask application init."""
        # noinspection PyProtectedMember
        if mongo_command_logger not in monitoring._LISTENERS.command_listeners:
            logger.error(self.config_error_message)
            return False
        return True

    def process_request(self, request) -> None:
        """Resets logger stats between each request."""
        mongo_command_logger.reset_tracker()

    def nav_title(self) -> str:
        """Debug toolbar in the bottom right corner."""
        return self.name

    def nav_subtitle(self) -> str:
        """Count operations total time."""
        if not self.is_properly_configured:
            self.has_content = False
            return self.config_error_message

        return (
            f"{mongo_command_logger.started_operations_count} operations, "
            f"in {mongo_command_logger.total_time * 0.001:.2f}ms"
        )

    def title(self) -> str:
        """Title for 'opened' debug panel window."""
        return "MongoDB Operations"

    def url(self) -> str:
        """Placeholder for internal URLs."""
        return ""

    def content(self) -> str:
        """Gathers all template required variables in one dict."""
        return self.render("panels/mongo-panel.html", self._context)
