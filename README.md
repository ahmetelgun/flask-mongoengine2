# Flask-MongoEngine2

[![PyPI version](https://badge.fury.io/py/flask-mongoengine2.svg)](https://badge.fury.io/py/flask-mongoengine2)
[![CI Tests](https://github.com/ahmetelgun/flask-mongoengine2/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/ahmetelgun/flask-mongoengine2/actions/workflows/tests.yml)
[![Documentation Status](https://readthedocs.org/projects/flask-mongoengine2/badge/?version=latest)](https://flask-mongoengine2.readthedocs.io/en/latest/?badge=latest)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/flask-mongoengine2)
![PyPI - Downloads](https://img.shields.io/pypi/dm/flask-mongoengine2)

Flask-MongoEngine2 is a Flask extension that provides integration with [MongoEngine]
and [FlaskDebugToolbar]:

- Connection management from Flask configuration, including multiple databases.
- `Document` classes with `get_or_404`, `first_or_404` and pagination helpers.
- Server side sessions stored in MongoDB.
- MongoDB panel for [FlaskDebugToolbar], based on [pymongo] command monitoring.

## Supported versions

| Dependency  | Version           |
|-------------|-------------------|
| Python      | 3.10 - 3.14       |
| Flask       | >= 3.1            |
| MongoEngine | >= 0.29.1, < 0.30 |
| PyMongo     | >= 4.18.3, < 5    |

Use version 2.x if you need older Python, Flask or MongoEngine versions.

## Installation

By default, Flask-MongoEngine2 installs integration only between [Flask] and
[MongoEngine]:

```bash
pip install flask-mongoengine2
```

Integration with [FlaskDebugToolbar] is optional and should be selected as extra
option, to limit amount of external dependencies in production environments:

```bash
pip install "flask-mongoengine2[toolbar]"
```

## Quickstart

```python
from flask import Flask
from flask_mongoengine2 import MongoEngine

app = Flask(__name__)
app.config["MONGODB_SETTINGS"] = [
    {
        "db": "project1",
        "host": "localhost",
        "port": 27017,
        "alias": "default",
    }
]
db = MongoEngine(app)  # or db = MongoEngine(); db.init_app(app)


class Todo(db.Document):
    title = db.StringField(max_length=60)
    comments = db.ListField(db.StringField())


@app.route("/todo/<todo_id>")
def show(todo_id):
    todo = Todo.objects.get_or_404(id=todo_id, _message_404="Todo not found")
    return todo.title


@app.route("/todos/<int:page>")
def todos(page):
    pagination = Todo.objects.paginate(page=page, per_page=10)
    return {"items": [t.title for t in pagination.items], "pages": pagination.pages}
```

Any MongoEngine field or helper is available on `db` (`db.StringField`,
`db.ReferenceField`, ...). `db.Document` and `db.DynamicDocument` use an extended
queryset with `get_or_404`, `first_or_404`, `paginate` and `paginate_field`.

## Flask configuration

Flask-MongoEngine2 does not provide any configuration defaults. User is responsible
for setting up correct database settings, to exclude any possible misconfiguration
and data corruption.

`MONGODB_SETTINGS` (a dict, or a list of dicts for multiple connections) is the
recommended way. Each dictionary is passed to `mongoengine.connect`, so any
[pymongo] `MongoClient` option can be used. Flat `MONGODB_*` keys are deprecated.

Please refer to [complete connection settings description] for more info.

## Sessions

```python
from flask_mongoengine2 import MongoEngineSessionInterface

app.session_interface = MongoEngineSessionInterface(db)
```

Session cookie follows Flask `SESSION_COOKIE_*` settings. Permanent sessions live
`PERMANENT_SESSION_LIFETIME`, others live `SESSION_TTL` (default `{"days": 1}`).

## Debug toolbar panel

```python
from pymongo import monitoring
from flask_mongoengine2.panels import mongo_command_logger

monitoring.register(mongo_command_logger)  # before database connection
app.config["DEBUG_TB_PANELS"] = ("flask_mongoengine2.panels.MongoDebugPanel",)
```

See [debug toolbar documentation] for details.

## Usage and API documentation

Full project documentation available on [read the docs].

## Contributing and testing

We are welcome for contributors and testers! Check [Contribution guidelines].

## License

Flask-MongoEngine2 is distributed under [BSD 3-Clause License].

[MongoEngine]: https://github.com/MongoEngine/mongoengine

[FlaskDebugToolbar]: https://github.com/pallets-eco/flask-debugtoolbar

[pymongo]: https://pymongo.readthedocs.io/en/stable/

[read the docs]: https://flask-mongoengine2.readthedocs.io/en/latest/

[complete connection settings description]: https://flask-mongoengine2.readthedocs.io/en/latest/flask_config.html

[debug toolbar documentation]: https://flask-mongoengine2.readthedocs.io/en/latest/debug_toolbar.html

[Flask]: https://github.com/pallets/flask

[BSD 3-Clause License]: LICENSE.md

[Contribution guidelines]: CONTRIBUTING.md
