"""Server side Flask sessions stored in MongoDB."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict

if TYPE_CHECKING:
    from flask import Flask, Request, Response

__all__ = ("MongoEngineSession", "MongoEngineSessionInterface")


class MongoEngineSession(CallbackDict, SessionMixin):
    def __init__(self, initial=None, sid: str | None = None):
        def on_update(self):
            self.modified = True

        super().__init__(initial, on_update)
        self.sid = sid
        self.modified = False


class MongoEngineSessionInterface(SessionInterface):
    """SessionInterface for mongoengine"""

    session_class = MongoEngineSession

    def __init__(self, db, collection: str = "session"):
        """
        The MongoSessionInterface

        :param db: The app's db eg: MongoEngine()
        :param collection: The session collection name defaults to "session"
        """

        if not isinstance(collection, str):
            raise ValueError("Collection argument should be string")

        class DBSession(db.Document):
            sid = db.StringField(primary_key=True)
            data = db.DictField()
            expiration = db.DateTimeField()
            meta = {
                "allow_inheritance": False,
                "collection": collection,
                "indexes": [
                    {
                        "fields": ["expiration"],
                        "expireAfterSeconds": 60 * 60 * 24 * 7 * 31,
                    }
                ],
            }

        self.cls = DBSession

    def get_expiration_time(self, app: Flask, session: SessionMixin) -> timedelta:
        if session.permanent:
            return app.permanent_session_lifetime
        # Fallback to 1 day session ttl, if SESSION_TTL not set.
        return timedelta(**app.config.get("SESSION_TTL", {"days": 1}))

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def open_session(self, app: Flask, request: Request) -> MongoEngineSession:
        sid = request.cookies.get(self.get_cookie_name(app))
        if sid:
            # Expiration is checked by the database, so expired sessions are never
            # loaded, regardless of the connection ``tz_aware`` setting.
            stored_session = (
                self.cls.objects(sid=sid, expiration__gt=self._now())
                .only("data")
                .first()
            )
            if stored_session is not None:
                return self.session_class(initial=stored_session.data, sid=sid)

        return self.session_class(sid=str(uuid.uuid4()))

    def save_session(
        self, app: Flask, session: MongoEngineSession, response: Response
    ) -> None:
        name = self.get_cookie_name(app)
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        secure = self.get_cookie_secure(app)
        samesite = self.get_cookie_samesite(app)
        httponly = self.get_cookie_httponly(app)
        partitioned = self.get_cookie_partitioned(app)

        # If the session is modified to be empty, remove the cookie and the record.
        # If the session is empty, return without setting the cookie.
        if not session:
            if session.modified:
                self.cls.objects(sid=session.sid).delete()
                response.delete_cookie(
                    name,
                    domain=domain,
                    path=path,
                    secure=secure,
                    samesite=samesite,
                    httponly=httponly,
                    partitioned=partitioned,
                )
            return

        if not self.should_set_cookie(app, session):
            return

        expiration = self._now() + self.get_expiration_time(app, session)

        if session.modified:
            self.cls(sid=session.sid, data=dict(session), expiration=expiration).save()
        else:
            # Cookie lifetime is refreshed, so the stored record must follow.
            self.cls.objects(sid=session.sid).update_one(set__expiration=expiration)

        response.set_cookie(
            name,
            session.sid,
            expires=expiration,
            httponly=httponly,
            domain=domain,
            path=path,
            secure=secure,
            samesite=samesite,
            partitioned=partitioned,
        )
