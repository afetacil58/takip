import os
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing

import app as core


class InitialSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = core.DB_PATH
        self.original_upload_dir = core.UPLOAD_DIR
        self.original_csrf_enabled = core.app.config["WTF_CSRF_ENABLED"]
        core.app.config["WTF_CSRF_ENABLED"] = False
        self.original_setup_token = os.environ.pop("SETUP_TOKEN", None)
        self.original_setup_token_file = os.environ.pop("SETUP_TOKEN_FILE", None)
        core.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        core.UPLOAD_DIR = os.path.join(self.temp_dir.name, "uploads")
        core.init_db()
        self.client = core.app.test_client()

    def tearDown(self):
        core.DB_PATH = self.original_db_path
        core.UPLOAD_DIR = self.original_upload_dir
        core.app.config["WTF_CSRF_ENABLED"] = self.original_csrf_enabled
        if self.original_setup_token is not None:
            os.environ["SETUP_TOKEN"] = self.original_setup_token
        if self.original_setup_token_file is not None:
            os.environ["SETUP_TOKEN_FILE"] = self.original_setup_token_file
        self.temp_dir.cleanup()

    def payload(self, **overrides):
        values = {
            "full_name": "Test Yönetici",
            "username": "test-admin",
            "email": "admin@example.test",
            "password": "a-long-test-password",
            "confirm_password": "a-long-test-password",
        }
        values.update(overrides)
        return values

    def test_first_admin_is_created_without_a_default_account(self):
        login = self.client.get("/login")
        setup = self.client.get("/setup")

        self.assertEqual(login.status_code, 302)
        self.assertEqual(login.location, "/setup")
        self.assertEqual(setup.status_code, 200)

        response = self.client.post("/setup", data=self.payload())

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")
        with closing(sqlite3.connect(core.DB_PATH)) as db:
            user = db.execute(
                "SELECT username, full_name, role, email FROM users"
            ).fetchone()
        self.assertEqual(
            user, ("test-admin", "Test Yönetici", "admin", "admin@example.test")
        )
        self.assertEqual(self.client.get("/setup").location, "/login")

    def test_docker_setup_token_is_required(self):
        os.environ["SETUP_TOKEN"] = "one-time-token"

        rejected = self.client.post(
            "/setup", data=self.payload(setup_token="wrong-token")
        )
        accepted = self.client.post(
            "/setup", data=self.payload(setup_token="one-time-token")
        )

        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(accepted.status_code, 302)
        with closing(sqlite3.connect(core.DB_PATH)) as db:
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(count, 1)

    def test_initial_password_below_previous_twelve_character_minimum_is_accepted(self):
        response = self.client.post(
            "/setup",
            data=self.payload(password="short", confirm_password="short"),
        )

        self.assertEqual(response.status_code, 302)
        with closing(sqlite3.connect(core.DB_PATH)) as db:
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(count, 1)

    def test_initial_password_rejects_three_characters(self):
        response = self.client.post(
            "/setup",
            data=self.payload(password="abc", confirm_password="abc"),
        )

        self.assertEqual(response.status_code, 200)
        with closing(sqlite3.connect(core.DB_PATH)) as db:
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(count, 0)

    def test_initial_password_accepts_exactly_four_characters(self):
        response = self.client.post(
            "/setup",
            data=self.payload(password="abcd", confirm_password="abcd"),
        )

        self.assertEqual(response.status_code, 302)
        with closing(sqlite3.connect(core.DB_PATH)) as db:
            count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        self.assertEqual(count, 1)

    def test_setup_requires_a_csrf_token(self):
        self.client.get("/setup")
        core.app.config["WTF_CSRF_ENABLED"] = True

        rejected = self.client.post("/setup", data=self.payload())
        page = self.client.get("/setup")
        csrf_token = re.search(
            r'name="csrf_token" value="([^"]+)"',
            page.get_data(as_text=True),
        ).group(1)
        accepted = self.client.post(
            "/setup", data=self.payload(csrf_token=csrf_token)
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(accepted.status_code, 302)

    def test_json_mutations_accept_the_csrf_header_only(self):
        self.client.get("/setup")
        core.app.config["WTF_CSRF_ENABLED"] = True

        rejected = self.client.post("/monthly-activities/period", json={"month": "2026-10"})
        page = self.client.get("/setup")
        csrf_token = re.search(
            r'name="csrf_token" value="([^"]+)"',
            page.get_data(as_text=True),
        ).group(1)
        accepted = self.client.post(
            "/monthly-activities/period",
            json={"month": "2026-10"},
            headers={"X-CSRFToken": csrf_token},
        )

        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(accepted.status_code, 302)
        self.assertIn("/login", accepted.location)

    def test_temporary_password_requires_change_before_dashboard(self):
        with closing(sqlite3.connect(core.DB_PATH)) as db:
            db.execute(
                """INSERT INTO users
                   (username, password_hash, full_name, role, department, must_change_password)
                   VALUES (?,?,?,?,?,1)""",
                (
                    "manager",
                    core.generate_password_hash("temporary-password"),
                    "Test Müdür",
                    "manager",
                    "Test Şube",
                ),
            )
            db.commit()

        login = self.client.post(
            "/login",
            data={"username": "manager", "password": "temporary-password"},
        )
        protected = self.client.get("/")
        password_page = self.client.get("/account/password")
        changed = self.client.post(
            "/account/password",
            data={
                "current_password": "temporary-password",
                "new_password": "abcd",
                "confirm_password": "abcd",
            },
        )
        dashboard = self.client.get("/")

        self.assertEqual(login.location, "/account/password")
        self.assertEqual(protected.location, "/account/password")
        self.assertEqual(password_page.status_code, 200)
        self.assertEqual(changed.location, "/")
        self.assertEqual(dashboard.status_code, 200)
        with closing(sqlite3.connect(core.DB_PATH)) as db:
            must_change = db.execute(
                "SELECT must_change_password FROM users WHERE username='manager'"
            ).fetchone()[0]
            audit_count = db.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
        self.assertEqual(must_change, 0)
        self.assertGreaterEqual(audit_count, 2)
        with closing(sqlite3.connect(core.DB_PATH)) as db:
            db.execute(
                "UPDATE users SET must_change_password=1 WHERE username='manager'"
            )
            db.commit()
        forced_again = self.client.get("/")
        self.assertEqual(forced_again.location, "/account/password")


if __name__ == "__main__":
    unittest.main()
