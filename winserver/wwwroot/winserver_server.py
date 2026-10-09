import os
import secrets
import sys


DATA_DIR = os.environ.get(
    "DATA_DIR", r"C:\ProgramData\AFAD\Takip\data"
)
os.makedirs(DATA_DIR, exist_ok=True)
os.environ["DATA_DIR"] = DATA_DIR
os.environ["DB_PATH"] = os.path.join(DATA_DIR, "gorev_takip.db")
os.environ["UPLOAD_DIR"] = os.path.join(DATA_DIR, "uploads")


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
    os.environ["SECRET_KEY"] = persistent_value(
        os.path.join(DATA_DIR, ".secret_key")
    )

import app

app.init_db()

setup_token_file = os.path.join(DATA_DIR, ".setup_token")
with app.app.app_context():
    has_users = app.get_db().execute("SELECT 1 FROM users LIMIT 1").fetchone()

setup_token = None
if not has_users:
    setup_token = persistent_value(setup_token_file)
    os.environ["SETUP_TOKEN"] = setup_token
else:
    os.environ.pop("SETUP_TOKEN", None)

if "--prepare-only" in sys.argv:
    if setup_token:
        print(f"Initial administrator setup token: {setup_token}")
    else:
        print("An administrator account already exists; no setup token is needed.")
    raise SystemExit(0)

from waitress import serve

port_value = os.environ.get("HTTP_PLATFORM_PORT")
if not port_value or not port_value.isdigit():
    raise RuntimeError("IIS HttpPlatformHandler did not provide HTTP_PLATFORM_PORT.")

serve(app.app, host="127.0.0.1", port=int(port_value), threads=8)
