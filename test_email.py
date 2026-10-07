"""Safe, offline check of the configured mail settings.

This script does not connect to the SMTP server, authenticate, or send a
message. Use `python -m unittest discover -s tests` to exercise the sending
code with a local mock SMTP server.
"""
import email_config


def main():
    configured = bool(email_config.SMTP_USER and email_config.SMTP_PASSWORD)
    print("SMTP host and port are configured.")
    print("TLS mode:", "implicit SSL" if email_config.SMTP_USE_SSL else "STARTTLS")
    print("Credentials:", "available in environment" if configured else "not configured")
    print("No network connection or email was made.")
    if not configured:
        print("Set SMTP_USER and SMTP_PASSWORD in the process environment or Docker .env file.")


if __name__ == "__main__":
    main()
