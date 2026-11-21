# Session Interface

To use MongoEngine as your session store simple configure the session interface:

```python
from flask_mongoengine2 import MongoEngine, MongoEngineSessionInterface

app = Flask(__name__)
db = MongoEngine(app)
app.session_interface = MongoEngineSessionInterface(db)
```

Session cookie respects Flask settings: `SESSION_COOKIE_NAME`, `SESSION_COOKIE_DOMAIN`,
`SESSION_COOKIE_PATH`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`,
`SESSION_COOKIE_SAMESITE` and `SESSION_COOKIE_PARTITIONED`.

- Permanent sessions live `PERMANENT_SESSION_LIFETIME`; other sessions live
  `SESSION_TTL` (`timedelta` keyword arguments, default `{"days": 1}`).
- With `SESSION_REFRESH_EACH_REQUEST` (Flask default), permanent sessions expiration
  is extended on each request, both in cookie and in database.
- Clearing the session removes both the cookie and the stored record.
