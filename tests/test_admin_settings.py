import os
import tempfile
import unittest
from contextlib import closing
from unittest.mock import MagicMock, patch

import app as core


class AdminSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = core.DB_PATH
        self.original_upload_dir = core.UPLOAD_DIR
        self.original_csrf_enabled = core.app.config["WTF_CSRF_ENABLED"]
        core.app.config["WTF_CSRF_ENABLED"] = False
        core.DB_PATH = os.path.join(self.temp_dir.name, "test.db")
        core.UPLOAD_DIR = os.path.join(self.temp_dir.name, "uploads")
        core.init_db()
        with closing(core.sqlite3.connect(core.DB_PATH)) as db:
            db.execute(
                """INSERT INTO users (username, password_hash, full_name, role, email)
                   VALUES ('admin', 'unused', 'Test Yönetici', 'admin', 'admin@example.test')"""
            )
            db.commit()
        self.client = core.app.test_client()
        with self.client.session_transaction() as session:
            session["user_id"] = 1
            session["role"] = "admin"
            session["full_name"] = "Test Yönetici"

    def tearDown(self):
        core.DB_PATH = self.original_db_path
        core.UPLOAD_DIR = self.original_upload_dir
        core.app.config["WTF_CSRF_ENABLED"] = self.original_csrf_enabled
        self.temp_dir.cleanup()

    def mail_settings(self, **overrides):
        data = {
            "email_notifications_enabled": "true",
            "smtp_host": "smtp.example.test",
            "smtp_port": "465",
            "smtp_user": "sender@example.test",
            "smtp_password": "secret-test-password",
            "mail_from_name": "Görev Takip",
            "base_url": "https://tasks.example.test",
            "smtp_use_ssl": "true",
        }
        data.update(overrides)
        return data

    def test_admin_can_save_smtp_and_application_settings(self):
        response = self.client.post(
            "/admin/settings", data=self.mail_settings()
        )

        self.assertEqual(response.status_code, 302)
        with core.app.test_request_context("/"):
            settings = core.get_email_settings()
        self.assertTrue(settings["email_notifications_enabled"])
        self.assertEqual(settings["smtp_host"], "smtp.example.test")
        self.assertEqual(settings["smtp_password"], "secret-test-password")
        self.assertEqual(settings["base_url"], "https://tasks.example.test")

    def test_smtp_password_is_not_rendered_back(self):
        self.client.post("/admin/settings", data=self.mail_settings())

        response = self.client.get("/admin/settings")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"secret-test-password", response.data)
        self.assertIn("Kayıtlı parola korunuyor".encode(), response.data)

    def test_blank_password_keeps_existing_smtp_password(self):
        self.client.post("/admin/settings", data=self.mail_settings())
        self.client.post(
            "/admin/settings",
            data=self.mail_settings(smtp_password="", email_notifications_enabled=""),
        )

        with core.app.test_request_context("/"):
            settings = core.get_email_settings()
        self.assertEqual(settings["smtp_password"], "secret-test-password")
        self.assertFalse(settings["email_notifications_enabled"])

    def test_test_email_uses_saved_settings(self):
        self.client.post("/admin/settings", data=self.mail_settings())
        smtp = MagicMock()
        with patch.object(core.smtplib, "SMTP_SSL") as smtp_ssl:
            smtp_ssl.return_value.__enter__.return_value = smtp
            response = self.client.post(
                "/admin/settings/test-email",
                data={"test_email": "recipient@example.test"},
            )

        self.assertEqual(response.status_code, 302)
        smtp_ssl.assert_called_once_with("smtp.example.test", 465, timeout=20)
        smtp.login.assert_called_once_with("sender@example.test", "secret-test-password")
        smtp.send_message.assert_called_once()

    def test_admin_page_rejects_manager(self):
        with closing(core.sqlite3.connect(core.DB_PATH)) as db:
            db.execute(
                """INSERT INTO users (username, password_hash, full_name, role)
                   VALUES ('manager', 'unused', 'Test Müdür', 'manager')"""
            )
            db.commit()
        with self.client.session_transaction() as session:
            session["user_id"] = 2
            session["role"] = "manager"

        response = self.client.get("/admin/settings")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")


if __name__ == "__main__":
    unittest.main()
