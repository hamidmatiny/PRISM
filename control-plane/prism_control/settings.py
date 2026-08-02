"""Django settings for PRISM control-plane."""

from __future__ import annotations

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DATA_ROOT = Path(os.environ.get("PRISM_DATA_ROOT", BASE_DIR.parent / ".data"))

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "prism-local-dev-only-not-for-production-change-me",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") not in {"0", "false", "False"}
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_q",
    "fleet",
    "review",
    "audit",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "prism_control.urls"
WSGI_APPLICATION = "prism_control.wsgi.application"

TEMPLATES = [
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

# Postgres via DATABASE_URL; SQLite fallback for local/ADR-001 zero-creds path.
_default_sqlite = f"sqlite:///{REPO_DATA_ROOT / 'control-plane' / 'db.sqlite3'}"
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL", _default_sqlite),
        conn_max_age=60,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CV review queue — same paths cv-service writes (Phase 3).
CV_REVIEW_PENDING_DIR = Path(
    os.environ.get(
        "PRISM_CV_REVIEW_PENDING_DIR",
        str(REPO_DATA_ROOT / "cv-review-queue" / "pending"),
    )
)
CV_REVIEW_DECIDED_DIR = Path(
    os.environ.get(
        "PRISM_CV_REVIEW_DECIDED_DIR",
        str(REPO_DATA_ROOT / "cv-review-queue" / "decided"),
    )
)
# Gold-layer writeback for reviewed findings (schema-valid CvFinding, reviewed=true).
CV_FINDINGS_GOLD_DIR = Path(
    os.environ.get(
        "PRISM_CV_FINDINGS_GOLD_DIR",
        str(REPO_DATA_ROOT / "cv-findings" / "gold"),
    )
)

# Django-Q2 — ORM broker so SQLite local works without Redis (see docs/ASYNC_TASKS.md).
Q_CLUSTER = {
    "name": "prism-control-plane",
    "workers": int(os.environ.get("PRISM_Q_WORKERS", "1")),
    "timeout": 90,
    "retry": 120,
    "queue_limit": 100,
    "bulk": 5,
    "orm": "default",
    "sync": os.environ.get("PRISM_Q_SYNC", "0") in {"1", "true", "True"},
    "catch_up": False,
}

PRISM_CONTROL_PLANE_PORT = int(os.environ.get("PRISM_CONTROL_PLANE_PORT", "9100"))

# Bootstrap demo users (management command / container entrypoint).
BOOTSTRAP_PASSWORD = os.environ.get("PRISM_BOOTSTRAP_PASSWORD", "prism-local-dev")
