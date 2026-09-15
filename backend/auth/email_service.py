import os
import requests
from dotenv import load_dotenv

load_dotenv()


def _send_email(to_email: str, subject: str, body: str) -> None:
    brevo_api_key = os.getenv("BREVO_API_KEY")
    smtp_from_email = os.getenv("SMTP_FROM_EMAIL")

    if not brevo_api_key:
        raise RuntimeError("BREVO_API_KEY is not configured")

    if not smtp_from_email:
        raise RuntimeError("SMTP_FROM_EMAIL is not configured")

    response = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": brevo_api_key,
            "content-type": "application/json",
        },
        json={
            "sender": {
                "email": smtp_from_email,
            },
            "to": [
                {
                    "email": to_email,
                }
            ],
            "subject": subject,
            "textContent": body,
        },
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            f"Brevo email API failed: {response.status_code} {response.text}"
        )


def send_verification_email(to_email: str, verification_url: str) -> None:
    _send_email(
        to_email=to_email,
        subject="Verify your RAG Chatbot account",
        body=f"""
Welcome to RAG Chatbot!

Please verify your email address by clicking the link below:

{verification_url}

This verification link will expire in 30 minutes.

If you did not create this account, you can ignore this email.
""",
    )


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    _send_email(
        to_email=to_email,
        subject="Reset your RAG Chatbot password",
        body=f"""
You requested a password reset for your RAG Chatbot account.

Click the link below to reset your password:

{reset_url}

This password reset link will expire in 30 minutes.

If you did not request a password reset, you can ignore this email.
""",
    )