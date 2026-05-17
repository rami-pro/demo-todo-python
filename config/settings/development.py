from .base import *  # noqa: F401, F403
from .base import REST_FRAMEWORK, env

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3"),
}

# Disable throttling in development so manual testing isn't blocked
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # type: ignore[index]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
