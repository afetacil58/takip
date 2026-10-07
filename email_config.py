"""SMTP configuration loaded from environment variables.

Keep SMTP credentials out of source control. Docker Compose reads them from
the ignored .env file; for a local run, set the same variables in the process
environment before starting the application.
"""
import os

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "true").strip().lower() in {
    "1", "true", "yes", "on"
}

FROM_NAME = os.environ.get("MAIL_FROM_NAME", "AFAD Görev Takip Sistemi")
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5000")
DAYS_AHEAD_WARNING = int(os.environ.get("DAYS_AHEAD_WARNING", "2"))
