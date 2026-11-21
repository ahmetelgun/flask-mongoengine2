from datetime import datetime, timedelta, timezone

import pytest
from flask import session
from pytest_mock import MockerFixture

from flask_mongoengine2 import MongoEngineSessionInterface

COOKIE = "session"


@pytest.fixture(autouse=True)
def setup_endpoints(app, db):
    app.session_interface = MongoEngineSessionInterface(db)

    @app.route("/")
    def index():
        session["a"] = "hello session"
        return session["a"]

    @app.route("/check-session")
    def check_session():
        return f"session: {session.get('a')}"

    @app.route("/clear")
    def clear():
        session.clear()
        return "cleared"


@pytest.fixture
def permanent_session_app(app):
    @app.before_request
    def make_session_permanent():
        # Set only once, so following requests do not modify the session.
        if not session.permanent:
            session.permanent = True

    return app


def _stored(app):
    return app.session_interface.cls.objects.first()


def test__save_session__called_on_session_set(app, mocker: MockerFixture):
    save_spy = mocker.spy(MongoEngineSessionInterface, "save_session")
    expiration_spy = mocker.spy(MongoEngineSessionInterface, "get_expiration_time")
    client = app.test_client()

    response = client.get("/")
    call_args, _ = expiration_spy.call_args_list[0]

    assert response.status_code == 200
    assert response.data.decode("utf-8") == "hello session"
    assert app.session_interface.cls.objects.count() == 1
    save_spy.assert_called_once()
    assert call_args[2].permanent is False  # session object


def test__save_session__called_on_session_set__should_respect_permanent_session_setting(
    permanent_session_app, mocker: MockerFixture
):
    expiration_spy = mocker.spy(MongoEngineSessionInterface, "get_expiration_time")
    client = permanent_session_app.test_client()
    client.get("/")

    call_args, _ = expiration_spy.call_args_list[0]
    assert call_args[2].permanent is True  # session object


def test__open_session_called_on_session_get(app, mocker: MockerFixture):
    client = app.test_client()
    open_spy = mocker.spy(MongoEngineSessionInterface, "open_session")
    client.get("/")
    open_spy.assert_called_once()  # On init call with no session

    response = client.get("/check-session")

    assert response.status_code == 200
    assert response.data.decode("utf-8") == "session: hello session"
    assert open_spy.call_count == 2  # On init + get with sid


def test__session_cookie__holds_sid_of_stored_record(app):
    client = app.test_client()
    client.get("/")
    cookie = client.get_cookie(COOKIE)
    assert cookie.value == _stored(app).sid
    assert _stored(app).data == {"a": "hello session"}


def test__empty_session__should_not_set_cookie_nor_store(app):
    client = app.test_client()
    response = client.get("/check-session")
    assert response.data.decode() == "session: None"
    assert "Set-Cookie" not in response.headers
    assert app.session_interface.cls.objects.count() == 0


def test__cleared_session__should_delete_cookie_and_record(app):
    client = app.test_client()
    client.get("/")
    assert app.session_interface.cls.objects.count() == 1

    response = client.get("/clear")

    assert app.session_interface.cls.objects.count() == 0
    assert client.get_cookie(COOKIE) is None
    assert "Max-Age=0" in response.headers["Set-Cookie"]


def test__expired_session__should_not_be_loaded(app):
    client = app.test_client()
    client.get("/")
    record = _stored(app)
    record.expiration = datetime.now(timezone.utc) - timedelta(seconds=1)
    record.save()

    response = client.get("/check-session")
    assert response.data.decode() == "session: None"


def test__unknown_sid__should_start_new_session(app):
    client = app.test_client()
    client.set_cookie(COOKIE, "not-existing-sid")
    response = client.get("/check-session")
    assert response.data.decode() == "session: None"


def test__session_ttl_config__is_respected(app):
    app.config["SESSION_TTL"] = {"hours": 2}
    client = app.test_client()
    before = datetime.now(timezone.utc).replace(tzinfo=None)
    client.get("/")
    expiration = _stored(app).expiration
    assert before + timedelta(hours=2) <= expiration + timedelta(seconds=1)
    assert expiration <= before + timedelta(hours=2, seconds=5)


def test__cookie_flags__follow_flask_config(app):
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_PATH="/app",
        SESSION_COOKIE_HTTPONLY=True,
    )
    response = app.test_client().get("/")
    header = response.headers["Set-Cookie"]
    assert "Secure" in header
    assert "SameSite=Strict" in header
    assert "Path=/app" in header
    assert "HttpOnly" in header


def test__custom_cookie_name__is_used(app):
    app.config["SESSION_COOKIE_NAME"] = "custom"
    client = app.test_client()
    client.get("/")
    assert client.get_cookie("custom") is not None
    assert client.get("/check-session").data.decode() == "session: hello session"


def test__unmodified_permanent_session__refreshes_stored_expiration(
    permanent_session_app, mocker: MockerFixture
):
    app = permanent_session_app
    client = app.test_client()
    client.get("/")
    record = _stored(app)
    old_expiration = datetime.now(timezone.utc) + timedelta(minutes=1)
    record.expiration = old_expiration
    record.save()

    save_spy = mocker.spy(app.session_interface.cls, "save")
    response = client.get("/check-session")

    save_spy.assert_not_called()
    assert response.data.decode() == "session: hello session"
    assert "Set-Cookie" in response.headers
    assert _stored(app).data == {"a": "hello session", "_permanent": True}
    assert _stored(app).expiration > old_expiration.replace(tzinfo=None)


def test__unmodified_non_permanent_session__does_not_touch_db_nor_cookie(
    app, mocker: MockerFixture
):
    client = app.test_client()
    client.get("/")
    save_spy = mocker.spy(app.session_interface.cls, "save")

    response = client.get("/check-session")

    assert "Set-Cookie" not in response.headers
    save_spy.assert_not_called()


@pytest.mark.parametrize("unsupported_value", (1, None, True, False, [], {}))
def test_session_interface__should_raise_value_error_if_collection_name_not_string(
    db, unsupported_value
):
    with pytest.raises(ValueError) as error:
        MongoEngineSessionInterface(db, collection=unsupported_value)

    assert str(error.value) == "Collection argument should be string"
