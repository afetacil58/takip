import os
import secrets


DATA_DIR = os.environ.get("DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
os.environ.setdefault("DB_PATH", os.path.join(DATA_DIR, "gorev_takip.db"))
os.environ.setdefault("UPLOAD_DIR", os.path.join(DATA_DIR, "uploads"))


def persistent_value(path):
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        with open(path, encoding="utf-8") as value_file:
            value = value_file.read().strip()
        if not value:
            raise RuntimeError(f"Persistent secret file is empty: {path}")
        return value

    value = secrets.token_hex(32)
    with os.fdopen(descriptor, "w", encoding="utf-8") as value_file:
        value_file.write(value + "\n")
    return value


if not os.environ.get("SECRET_KEY"):
    os.environ["SECRET_KEY"] = persistent_value(os.path.join(DATA_DIR, ".secret_key"))

import app

app.init_db()

setup_token_file = os.environ.get(
    "SETUP_TOKEN_FILE", os.path.join(DATA_DIR, ".setup_token")
)
with app.app.app_context():
    has_users = app.get_db().execute("SELECT 1 FROM users LIMIT 1").fetchone()

if not has_users:
    setup_token = persistent_value(setup_token_file)
    os.environ["SETUP_TOKEN"] = setup_token
    print(
        "Initial administrator setup token (enter it at /setup): "
        + setup_token,
        flush=True,
    )

os.execvp(
    "gunicorn",
    ["gunicorn", "--preload", "-w", "4", "-b", "0.0.0.0:5000", "wsgi:app"],
)
