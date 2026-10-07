import unittest
from unittest.mock import MagicMock, patch

import app


class EmailDeliveryTests(unittest.TestCase):
    def test_ssl_delivery_uses_configured_smtp_values(self):
        cfg = app.mail_cfg
        smtp = MagicMock()
        with patch.object(cfg, "SMTP_USER", "sender@example.test"), patch.object(
            cfg, "SMTP_PASSWORD", "mock-password"
        ), patch.object(app, "EMAIL_ENABLED", True), patch.object(
            app.smtplib, "SMTP_SSL"
        ) as smtp_ssl:
            smtp_ssl.return_value.__enter__.return_value = smtp
            with patch.object(cfg, "SMTP_USE_SSL", True):
                sent = app.send_email("recipient@example.test", "Test", "Body")

        self.assertTrue(sent)
        smtp_ssl.assert_called_once_with(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=20)
        smtp.login.assert_called_once_with("sender@example.test", "mock-password")
        smtp.send_message.assert_called_once()

    def test_starttls_delivery_uses_configured_smtp_values(self):
        cfg = app.mail_cfg
        smtp = MagicMock()
        with patch.object(cfg, "SMTP_USER", "sender@example.test"), patch.object(
            cfg, "SMTP_PASSWORD", "mock-password"
        ), patch.object(app, "EMAIL_ENABLED", True), patch.object(
            app.smtplib, "SMTP"
        ) as smtp_plain:
            smtp_plain.return_value.__enter__.return_value = smtp
            with patch.object(cfg, "SMTP_USE_SSL", False):
                sent = app.send_email("recipient@example.test", "Test", "Body")

        self.assertTrue(sent)
        smtp_plain.assert_called_once_with(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=20)
        smtp.starttls.assert_called_once_with()
        smtp.login.assert_called_once_with("sender@example.test", "mock-password")
        smtp.send_message.assert_called_once()

    def test_disabled_email_does_not_open_smtp_connection(self):
        with patch.object(app, "EMAIL_ENABLED", False), patch.object(
            app.smtplib, "SMTP_SSL"
        ) as smtp_ssl:
            self.assertFalse(app.send_email("recipient@example.test", "Test", "Body"))
        smtp_ssl.assert_not_called()


if __name__ == "__main__":
    unittest.main()
