"""Django settings. Everything that differs between a laptop and a server comes from the environment or a gitignored
`.env` file (copy `.env.example`). With DEBUG off the security settings switch on by themselves."""
from datetime import timedelta
from pathlib import Path

import environ

from program import runtime

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")        # real environment variables win over the file

SECRET_KEY = env("SECRET_KEY")                  # required: no default on purpose
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
ADMIN_URL = env("ADMIN_URL", default="admin/")  # keep the trailing slash; change it in production

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "constance",
    "axes",
    "program",
    "pages",
    "accounts",
    "ledger",
    "projects",
    "submissions",
    "shop",
    "guides",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "submissions.middleware.CollectFirst",     # a result waiting at Grandma's goes before the pages that matter (docs/submissions.md)
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",          # last: turns a lockout into the themed 429 page
]

ROOT_URLCONF = "grandma.urls"
WSGI_APPLICATION = "grandma.wsgi.application"
ASGI_APPLICATION = "grandma.asgi.application"

# The site's own templates use Jinja2 (macros, identical output to the Flask version). The Django engine second, with
# APP_DIRS, only so the admin keeps its templates. A name that Jinja2 cannot find falls through to the Django engine.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": False,
        "OPTIONS": {
            "environment": "grandma.jinja.environment",
            "context_processors": ["pages.context.context"],
        },
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# IMMEDIATE: a write transaction takes SQLite's write lock when it starts, so "read the balance, then add an entry" in
# ledger/services.py cannot interleave with another writer. (On Postgres select_for_update does this job.)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3",
                         "OPTIONS": {"transaction_mode": "IMMEDIATE"}}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Settings staff edit in the admin ("Constance"), stored in the database. What they are and their defaults: program/runtime.py.
CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"
CONSTANCE_CONFIG = runtime.CONFIG
CONSTANCE_CONFIG_FIELDSETS = runtime.FIELDSETS
CONSTANCE_ADDITIONAL_FIELDS = dict(runtime.FIELDS)

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"          # collectstatic target for a real server (gitignored)

# Uploads (the screenshots people hand in, submissions/images.py). Outside static, gitignored. Django serves them only with
# DEBUG on (grandma/urls.py); a real server must serve MEDIA_ROOT itself, as plain images (docs/submissions.md, docs/security.md).
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "media/"

# Login. Accounts are made in the admin (no signup). Axes locks a username from an address after repeated failures, on /login/ and
# the admin alike. The lock is per (username, IP address) so one person's typos never lock out a school's shared address.
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend"]
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(minutes=env.int("AXES_COOLOFF_MINUTES", default=30))
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_DISABLE_ACCESS_LOG = True                     # do not keep a log of every successful sign-in (IP addresses of minors): only failures are kept, to count them
AXES_LOCKOUT_TEMPLATE = "pages/locked.html"        # answered with HTTP 429

# Cookies: the session cookie is HttpOnly and SameSite=Lax (Django's defaults, stated so they stay), the CSRF cookie too and
# HttpOnly as well (no script of ours reads it: every POST form carries its own token).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

# Production security: on whenever DEBUG is off, each one can be overridden from the environment.
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=not DEBUG)
if env.bool("BEHIND_PROXY", default=False):     # set when a reverse proxy terminates HTTPS and sets X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
