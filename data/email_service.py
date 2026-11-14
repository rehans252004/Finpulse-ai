"""Email delivery for FinPulse account notifications."""
import os
import smtplib
import ssl
from email.message import EmailMessage


class EmailConfigurationError(ValueError):
    """Raised when SMTP credentials or settings are missing or invalid."""


def send_welcome_email(recipient, signin_url):
    host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "").strip()
    sender = os.getenv("SMTP_FROM_EMAIL", username).strip()
    port_value = os.getenv("SMTP_PORT", "587").strip()

    if not host or not username or not password or not sender:
        raise EmailConfigurationError(
            "Set SMTP_USERNAME, SMTP_PASSWORD, and SMTP_FROM_EMAIL."
        )

    try:
        port = int(port_value)
    except ValueError as error:
        raise EmailConfigurationError("SMTP_PORT must be a valid port number.") from error
    if not 1 <= port <= 65535:
        raise EmailConfigurationError("SMTP_PORT must be between 1 and 65535.")

    message = EmailMessage()
    message["Subject"] = "Welcome to FinPulse AI"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "Welcome to FinPulse AI!\n\n"
        "Your account has been created. You can sign in to your dashboard here:\n"
        f"{signin_url}\n\n"
        "If you did not create this account, you can ignore this message."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(username, password)
        smtp.send_message(message)
