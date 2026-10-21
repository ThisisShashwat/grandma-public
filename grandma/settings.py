"""Django settings. Everything that differs between a laptop and a server comes from the environment or a gitignored
`.env` file (copy `.env.example`). With DEBUG off the security settings switch on by themselves."""
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import re

import environ
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

from program import runtime

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")        # real environment variables win over the file

SECRET_KEY = env("SECRET_KEY")                  # required: no default on purpose
DEBUG = env.bool("DEBUG", default=False)
if not DEBUG and SECRET_KEY.startswith("dev-only"):      # the key in .env.example is public: a server must never run on it
    raise ImproperlyConfigured("SECRET_KEY is the public development key from .env.example. Make a long random one (the command is in .env.example) before turning DEBUG off.")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
if not DEBUG and not ALLOWED_HOSTS:       # with no host Django answers every request with a 400 and no hint why
    raise ImproperlyConfigured("Set ALLOWED_HOSTS to the site's host name (comma separated, in the environment) before turning DEBUG off: with none, every request is refused with a 400.")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
PUBLIC_PAGE_CACHE_SECONDS = env.int("PUBLIC_PAGE_CACHE_SECONDS", default=60)     # Cache-Control max-age of the home page and the guides (pages/public_cache.py); 0 = off
LIVE_CACHE_SECONDS = env.int("LIVE_CACHE_SECONDS", default=15)     # how long pages.live.live() keeps the admin settings in memory; 0 = ask the database every time (the tests)
ADMIN_URL = env("ADMIN_URL", default="admin/")  # keep the trailing slash; change it in production
if not ADMIN_URL.endswith("/") or ADMIN_URL.startswith("/"):
    raise ImproperlyConfigured("ADMIN_URL must end with a slash and must not start with one, like admin/ or a-long-secret-word/.")
if not DEBUG and ADMIN_URL == "admin/":
    raise ImproperlyConfigured("Set ADMIN_URL to a long secret path (ending with a trailing slash) in the environment before turning DEBUG off.")
SITE_URL = env("SITE_URL", default="http://localhost:8000")      # the public address, for links in messages sent outside a request (submissions/notices.py) and the redirect addresses of Hack Club and Hackatime
_site = urlsplit(SITE_URL)
if _site.scheme not in ("http", "https") or not _site.hostname or "@" in _site.netloc or _site.path not in ("", "/") or _site.query or _site.fragment:
    raise ImproperlyConfigured("SITE_URL must be the bare address of the site, like https://grandma.example.com: http or https, a host, no path, query or login.")
if not DEBUG and _site.scheme != "https":
    raise ImproperlyConfigured("SITE_URL must start with https:// while DEBUG is off: Hack Club and Hackatime send people (and their codes) back to it.")
PREVIEW_PASSWORD = env("PREVIEW_PASSWORD", default="")           # a private preview: HTTP Basic password for the whole site (pages/preview_gate.py). A secret: environment only. Empty is off
if PREVIEW_PASSWORD and len(PREVIEW_PASSWORD) < 12:
    raise ImproperlyConfigured("PREVIEW_PASSWORD must be at least 12 characters long (or empty, which switches the preview gate off).")
SLACK_BOT_TOKEN = env("SLACK_BOT_TOKEN", default="")             # the program's Slack bot (accounts/slack.py). A secret: environment only, never the admin or the database
SLACK_SYNC = env.bool("SLACK_SYNC", default=False)               # False: a Slack call runs in a short lived background thread, never in the request. True: it runs at once, in the caller (the tests, pytest.ini)
HCA_CLIENT_ID = env("HCA_CLIENT_ID", default="")                 # Sign in with Hack Club (accounts/hca.py). The id and the secret: environment only, never the admin or the database
HCA_CLIENT_SECRET = env("HCA_CLIENT_SECRET", default="")
HCA_ISSUER = env("HCA_ISSUER", default="https://auth.hackclub.com")
HACKATIME_CLIENT_ID = env("HACKATIME_CLIENT_ID", default="")             # Connecting a Hackatime account (accounts/hackatime.py). The id and the secret: environment only, never the admin or the database
HACKATIME_CLIENT_SECRET = env("HACKATIME_CLIENT_SECRET", default="")
HACKATIME_BASE_URL = env("HACKATIME_BASE_URL", default="https://hackatime.hackclub.com")


def validate_hackatime_token_keys(keys):
    from cryptography.fernet import Fernet
    for key in keys:
        try:
            Fernet(key)
        except Exception:
            raise ImproperlyConfigured("HACKATIME_TOKEN_KEYS contains an invalid Fernet key.")


HCA_IDENTITY = env.bool("HCA_IDENTITY", default=False)     # ask Hack Club for birthdate and address too and keep name, birthday and address ENCRYPTED (accounts/identity.py); needs PII_KEYS and an app Hack Club has marked official (the owner's is)
PII_KEYS = env.list("PII_KEYS", default=[])                # comma separated Fernet keys, newest first, environment only: they open Profile.identity (python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
STAFF_SLACK_IDS = env.list("STAFF_SLACK_IDS", default=[])  # the ONLY people who become staff and superuser: a Hack Club sign-in whose verified Slack ID is listed here (accounts/hca.py grant_staff). Nothing else makes an admin
if any(not re.fullmatch(r"[UW][A-Z0-9]{8,11}", _id) for _id in STAFF_SLACK_IDS):
    raise ImproperlyConfigured("STAFF_SLACK_IDS must be comma separated Slack member IDs such as U01ABC23DEF.")
validate_hackatime_token_keys(PII_KEYS)                    # the same check: a malformed key stops Django at startup
HACKATIME_TOKEN_KEYS = env.list("HACKATIME_TOKEN_KEYS", default=[])          # comma separated Fernet keys, newest first, environment only, never derived from SECRET_KEY, never in the admin or the database
validate_hackatime_token_keys(HACKATIME_TOKEN_KEYS)
for _name, _address in (("HCA_ISSUER", HCA_ISSUER), ("HACKATIME_BASE_URL", HACKATIME_BASE_URL)):
    if not DEBUG and not _address.startswith("https://"):
        raise ImproperlyConfigured(f"{_name} must start with https:// while DEBUG is off: codes and tokens travel to it.")

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
    "audit",
    "projects",
    "submissions",
    "shop",
    "orders",
    "guides",
    "metrics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "pages.preview_gate.preview_gate",                 # an optional password in front of everything below, static files included (PREVIEW_PASSWORD, empty is off)
    "pages.static_cache.static_cache",                 # one year for a static address with ?v=, one hour without (replaces WhiteNoise's header)
    "whitenoise.middleware.WhiteNoiseMiddleware",      # serves the collected static files with DEBUG off (a real server may serve STATIC_ROOT itself instead)
    "pages.probes.probes",                             # /healthz and /readyz answer whatever Host header the host's probe sends (Django would refuse a pod address with a 400)
    "pages.body_cap.body_cap",                         # a body that says it is too big is refused before anything reads it (FORM_BODY_MAX_KB, UPLOAD_BODY_MAX_MB)
    "pages.rate_limit.rate_limit",                     # after WhiteNoise, so static files are never counted (RATE_LIMITS_ENABLED and the RATE_LIMIT_* numbers)
    "metrics.visits.count_visits",                     # counts views of four public pages per day, after the response is built, only with COUNT_VISITS on (touches no session, no cookie, no query)
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "audit.middleware.RequestId",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "accounts.signed_in_flag.signed_in_flag",      # the plain "signed in" hint cookie the public pages' header reads (they never touch the session)
    "accounts.admin_gate.admin_gate",          # gates the admin address (docs/owner.md 2026-10-05)
    "submissions.middleware.CollectFirst",     # a result waiting at Grandma's goes before the pages that matter (docs/submissions.md)
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "pages.middleware.method_not_allowed_page",    # a plain 405 gets Grandma's page (after the session and auth, so the header knows who is here)
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
                "django.template.context_processors.csp",      # the admin's one inline <style> carries this nonce
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Development: the SQLite file. Production: DATABASE_URL, the address the host gives (needs its driver, for example psycopg, in requirements).
DATABASES = {"default": env.db("DATABASE_URL") if env("DATABASE_URL", default="") else {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
# IMMEDIATE: a write transaction takes SQLite's write lock when it starts, so "read the balance, then add an entry" in
# ledger/services.py cannot interleave with another writer. (On Postgres select_for_update does this job.)
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})["transaction_mode"] = "IMMEDIATE"
else:      # a network database: keep each connection for a while instead of a new TLS handshake per request, and drop a dead one before use
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Settings staff edit in the admin ("Constance"), stored in the database. What they are and their defaults: program/runtime.py.
CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"
# SETTING_DEFAULTS: what an admin setting is while nobody has saved it in the admin of THIS environment, as comma separated KEY=value pairs, for example
# SETTING_DEFAULTS=HCA_LOGIN=true,HACKATIME_ENABLED=true. The code defaults (program/runtime.py) and the tests stay as they are; a value saved in the admin always wins.
# It is how a fresh server gets Hack Club sign-in on before anybody can reach the admin (the admin needs a staff account, which needs the sign-in).
_defaults = {}
for _pair in env.list("SETTING_DEFAULTS", default=[]):
    _key, _, _value = _pair.partition("=")
    if _key not in runtime.CONFIG or not _value:
        raise ImproperlyConfigured(f"SETTING_DEFAULTS: '{_pair}' is not KEY=value for a known admin setting.")
    _kind = type(runtime.CONFIG[_key][0])
    if _kind is bool:
        if _value.lower() not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
            raise ImproperlyConfigured(f"SETTING_DEFAULTS: {_key} must be true or false.")
        _defaults[_key] = _value.lower() in ("true", "1", "yes", "on")
    else:
        try:
            _defaults[_key] = _kind(_value)
        except ValueError:
            raise ImproperlyConfigured(f"SETTING_DEFAULTS: {_key} must be a {_kind.__name__}.") from None
CONSTANCE_CONFIG = {key: (_defaults.get(key, row[0]), *row[1:]) for key, row in runtime.CONFIG.items()}
CONSTANCE_CONFIG_FIELDSETS = runtime.FIELDSETS
CONSTANCE_ADDITIONAL_FIELDS = dict(runtime.FIELDS)

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Asia/Kolkata")    # the admin's default zone for times (stored values stay UTC, USE_TZ); a staff member with a time zone on their Profile sees their own (accounts/admin_gate.py); the dashboard uses each person's own zone
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"          # collectstatic target for a real server (gitignored)
# Compressed, not the manifest storage: some CSS names art files that do not exist yet (favicon.png, cursor-spoon.png, fridge.png) and the manifest storage fails collectstatic on them.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

# PUBLIC uploads on Cloudflare R2 (S3 compatible). All five or none: with none, uploads stay in MEDIA_ROOT as before. The keys are SECRETS (environment only).
# Only the public screenshots go there. Order proofs (PRIVATE_MEDIA_ROOT, orders/storage.py) never do: they use their own storage class.
R2_ENDPOINT_URL = env("R2_ENDPOINT_URL", default="")         # https://<account id>.r2.cloudflarestorage.com
R2_BUCKET = env("R2_BUCKET", default="")
R2_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID", default="")
R2_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY", default="")
R2_PUBLIC_URL = env("R2_PUBLIC_URL", default="").rstrip("/")  # where the bucket is readable by anybody: https://pub-xxxx.r2.dev or your own domain, no path
_r2 = (R2_ENDPOINT_URL, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_PUBLIC_URL)
if any(_r2) and not all(_r2):
    raise ImproperlyConfigured("R2 needs all five of R2_ENDPOINT_URL, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_PUBLIC_URL, or none of them.")
R2_ENABLED = all(_r2)
_r2_public = urlsplit(R2_PUBLIC_URL)
if R2_ENABLED:
    if urlsplit(R2_ENDPOINT_URL).scheme != "https" or _r2_public.scheme != "https" or not _r2_public.netloc or _r2_public.path or _r2_public.query:
        raise ImproperlyConfigured("R2_ENDPOINT_URL and R2_PUBLIC_URL must be https addresses, and R2_PUBLIC_URL must have no path or query.")
    from botocore.config import Config as _BotoConfig
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": R2_BUCKET, "endpoint_url": R2_ENDPOINT_URL, "access_key": R2_ACCESS_KEY_ID, "secret_key": R2_SECRET_ACCESS_KEY,
            "region_name": "auto", "signature_version": "s3v4", "custom_domain": _r2_public.netloc, "url_protocol": "https:",
            "querystring_auth": False, "default_acl": None, "file_overwrite": False,       # public, plain addresses; random names are never overwritten
            "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},      # the names are random and never reused
            "client_config": _BotoConfig(request_checksum_calculation="when_required", response_checksum_validation="when_required"),      # R2 does not take the newer default checksums
        },
    }

# Uploads (the screenshots people hand in, submissions/images.py). Outside static, gitignored. Django serves them only when SERVE_MEDIA
# is on (grandma/urls.py); a real server must serve MEDIA_ROOT itself, as plain images (docs/submissions.md, docs/security.md).
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))      # on a host: the persistent folder for PUBLIC uploads
MEDIA_URL = "media/"
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=DEBUG)      # for a private preview only: real production serves media/ from the web server, and PRIVATE_MEDIA_ROOT is never served by this
# PRIVATE uploads (cart and part screenshots of an order, orders/storage.py): outside static, outside MEDIA_ROOT, gitignored, never
# served as a file. Only the authenticated view orders/views.py hands them out. A web server must NOT expose this folder (docs/orders.md).
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))
DATA_UPLOAD_MAX_NUMBER_FILES = 25
if PRIVATE_MEDIA_ROOT.resolve() == MEDIA_ROOT.resolve() or MEDIA_ROOT.resolve() in PRIVATE_MEDIA_ROOT.resolve().parents:
    raise ImproperlyConfigured("PRIVATE_MEDIA_ROOT must not be MEDIA_ROOT or inside it: the private order proofs would be served as public files.")
SECURE_REDIRECT_EXEMPT = [r"^healthz/?$", r"^readyz/?$"]       # the host's health probes may use plain http

# Login. With Hack Club sign-in on, /login/ redirects to Hack Club and there is no password form; the form exists only
# while it is off. Axes guards the password forms that exist (development login, and the admin's own login for the superuser).
# The lock is per (username, IP address) so one person's typos never lock out a school's shared address.
# The public password form on /login/ exists only in development; production has none, the superuser uses the admin's own login page behind the secret admin address.
PASSWORD_LOGIN = env.bool("PASSWORD_LOGIN", default=DEBUG)
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "django.contrib.auth.backends.ModelBackend"]
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = timedelta(minutes=env.int("AXES_COOLOFF_MINUTES", default=30))
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = False    # a failed try while locked must not restart the cool-off, or a stranger could keep a name locked for good
TRUSTED_PROXY_COUNT = env.int("AXES_PROXY_COUNT", default=0)    # 0: the address is REMOTE_ADDR and X-Forwarded-For is ignored. N: N trusted reverse proxies stand in front (accounts/clientip.py)
AXES_CLIENT_IP_CALLABLE = "accounts.clientip.client_ip"
AXES_DISABLE_ACCESS_LOG = True                     # do not keep a log of every successful sign-in (IP addresses of minors): only failures are kept, to count them
AXES_LOCKOUT_TEMPLATE = "pages/locked.html"        # answered with HTTP 429

# Cookies: the session cookie is HttpOnly and SameSite=Lax (Django's defaults, stated so they stay), the CSRF cookie too and
# HttpOnly as well (no script of ours reads it: every POST form carries its own token).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_FAILURE_VIEW = "pages.views.csrf_failure"      # Grandma's "stale slip" page (HTTP 403)

# Request limits (pages/body_cap.py, pages/rate_limit.py). Bodies: only the three picture pages may be big. Rates per minute; every number can be changed in the environment.
FORM_BODY_MAX_KB = env.int("FORM_BODY_MAX_KB", default=128)
UPLOAD_BODY_MAX_MB = env.int("UPLOAD_BODY_MAX_MB", default=22)         # above the biggest admin allowed screenshot (20 MB) plus the form around it
RATE_LIMITS_ENABLED = env.bool("RATE_LIMITS_ENABLED", default=True)
METRICS_ENABLED = env.bool("METRICS_ENABLED", default=True)           # the activity and visit counters of the admin Metrics page; the test suite switches it off like RATE_LIMITS_ENABLED
RATE_LIMIT_GET = env.int("RATE_LIMIT_GET", default=1200)                # a GET per address, counted in each worker's memory (a school or a carrier shares one address)
RATE_LIMIT_POST_IP = env.int("RATE_LIMIT_POST_IP", default=600)        # a POST per address (a school or a carrier may share one)
RATE_LIMIT_POST_SESSION = env.int("RATE_LIMIT_POST_SESSION", default=60)
RATE_LIMIT_SIGN_IN = env.int("RATE_LIMIT_SIGN_IN", default=300)        # the sign-in and connect addresses, per address (a whole class may sign in at once)
# The shared counter: a database table (made by `manage.py createcachetable`, which the Dockerfile runs at start) so every worker agrees; local memory in development.
CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "ratelimit_local": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "ratelimit-get", "OPTIONS": {"MAX_ENTRIES": 20000}},
    "ratelimit": ({"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "ratelimit-post"} if DEBUG else
                  {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "grandma_ratelimit", "OPTIONS": {"MAX_ENTRIES": 50000, "CULL_FREQUENCY": 4}}),
}

# Production security: on whenever DEBUG is off, each one can be overridden from the environment.
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=not DEBUG)
BEHIND_PROXY = env.bool("BEHIND_PROXY", default=False)
if BEHIND_PROXY:     # set when a reverse proxy terminates HTTPS and sets X-Forwarded-Proto
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Content Security Policy (Django's own, django.middleware.csp): what a page may load and run. Enforced; CSP_REPORT_ONLY=True in the
# environment only reports to the browser console, to look before blocking. Scripts: our own files and the libraries in templates/base.html,
# each by its exact address (a bare host would allow any npm package on that CDN; tests/test_csp.py pins this list to the template). No inline
# script or handler exists and eval is never allowed. style-src-attr lets the style="--x: 36" attributes (custom properties) through and
# nothing else inline except one hashed <style> (below). form-action also names the Hackatime host and the Hack Club Auth host: Chrome applies it to the redirects
# that follow a form POST, and the hours picker's POST ends in a redirect through the connect flow to Hackatime (and, for somebody signed out there, on to Hack Club
# to sign in) when Hackatime has rejected the stored token (not verified in a browser: it needs live credentials). The hours check itself no longer goes to
# Hackatime: it reads with the stored token on the server. Sign in with Hack Club and the Hackatime connect are plain links, so they need nothing here.
CSP_REPORT_ONLY = env.bool("CSP_REPORT_ONLY", default=False)
CSP_SCRIPTS = [f"https://cdn.jsdelivr.net/npm/{file}" for file in (
    "gsap@3.15.0/dist/gsap.min.js", "gsap@3.15.0/dist/ScrollTrigger.min.js", "gsap@3.15.0/dist/Draggable.min.js",
    "rough-notation@0.5.1/lib/rough-notation.iife.js", "canvas-confetti@1.9.4/dist/confetti.browser.js")]
ROUGH_NOTATION_STYLE = "'sha256-a2IHEXu1qFG5AB5vTDZCiFizZFFc0ZNcwdq6s6vt3Og='"      # the one <style> rough-notation 0.5.1 adds itself (the draw-in keyframes): without it the marks stay invisible
_hackatime, _hca = urlsplit(HACKATIME_BASE_URL), urlsplit(HCA_ISSUER)
CSP_POLICY = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, *CSP_SCRIPTS],
    "style-src": [CSP.SELF, CSP.NONCE, ROUGH_NOTATION_STYLE],
    "style-src-attr": [CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:", *([f"https://{_r2_public.netloc}"] if R2_ENABLED else [])],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "form-action": [CSP.SELF, f"{_hackatime.scheme}://{_hackatime.netloc}", f"{_hca.scheme}://{_hca.netloc}"],
}
SECURE_CSP = {} if CSP_REPORT_ONLY else CSP_POLICY
SECURE_CSP_REPORT_ONLY = CSP_POLICY if CSP_REPORT_ONLY else {}

# Errors go to stderr (the server's log), also with DEBUG off, where Django would otherwise log nothing. Messages only (the path and the
# traceback): never a request body, a header or a form value.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"short": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "short"}},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
