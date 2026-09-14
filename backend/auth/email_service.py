import os
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()


def _send_email(
    to_email: str,
    subject: str,
    body: str,
) -> None:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL")

    if not all([
        smtp_host,
        smtp_username,
        smtp_password,
        smtp_from_email,
    ]):
        raise RuntimeError("SMTP configuration is incomplete")

    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = smtp_from_email
    message["To"] = to_email

    message.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(message)


def send_verification_email(to_email: str, verification_url: str) -> None:
    _send_email(
        to_email=to_email,
        subject="Verify your RAG Chatbot account",
        body=f"""
Hello,

Thank you for registering for RAG Chatbot.

Please verify your email address by clicking the link below:

{verification_url}

This verification link will expire soon.

If you did not create this account, you can safely ignore this email.

Regards,
RAG Chatbot
""",
    )


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    _send_email(
        to_email=to_email,
        subject="Reset your RAG Chatbot password",
        body=f"""
Hello,

We received a request to reset the password for your RAG Chatbot account.

Please reset your password by clicking the link below:

{reset_url}

This password reset link will expire soon.

If you did not request a password reset, you can safely ignore this email.
Your current password will remain unchanged.

Regards,
RAG Chatbot
""",
    )
