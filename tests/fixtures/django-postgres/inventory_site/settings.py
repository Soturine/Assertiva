"""PostgreSQL only: the tests use PostgreSQL features. The connection comes from DATABASE_URL (local default)."""
import os
from urllib.parse import urlsplit

url = urlsplit(os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/postgres"))
SECRET_KEY = "fixture-only-not-a-secret"
DEBUG = False
INSTALLED_APPS = ["django.contrib.contenttypes", "stock"]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": url.path.lstrip("/") or "postgres",
        "USER": url.username or "",
        "PASSWORD": url.password or "",
        "HOST": url.hostname or "",
        "PORT": str(url.port or ""),
    }
}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
