from fastapi import APIRouter, Depends, HTTPException
from backend.auth.dependencies import get_current_user
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import User, PasswordHistory

from backend.auth.security import (
    hash_password,
    verify_password,
    create_access_token
)

from backend.auth.email_service import (
    send_verification_email,
    send_password_reset_email,
)

import secrets
import hashlib
import os
from datetime import datetime, timedelta

from google.oauth2 import id_token
from google.auth.transport import requests


# ============================================================
# Router
# ============================================================

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# ============================================================
# Request models
# ============================================================

class RegisterRequest(BaseModel):

    email: EmailStr
    password: str


class LoginRequest(BaseModel):

    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):

    credential: str


class VerifyEmailRequest(BaseModel):

    token: str


class ForgotPasswordRequest(BaseModel):

    email: EmailStr


class ResetPasswordRequest(BaseModel):

    token: str
    new_password: str


# ============================================================
# Register
# ============================================================

@router.post("/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):

    if len(request.password) < 6:

        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 6 characters."
        )


    if len(request.password.encode("utf-8")) > 72:

        raise HTTPException(
            status_code=400,
            detail="Password must be 72 bytes or fewer."
        )


    existing_user = db.query(
        User
    ).filter(
        User.email == request.email
    ).first()


    if existing_user:

        raise HTTPException(
            status_code=400,
            detail="Email already registered."
        )


    # --------------------------------------------------------
    # Generate secure email verification token
    # --------------------------------------------------------

    verification_token = secrets.token_urlsafe(32)

    verification_token_hash = hashlib.sha256(
        verification_token.encode("utf-8")
    ).hexdigest()

    verification_expires_at = (
        datetime.utcnow() + timedelta(minutes=30)
    )


    # --------------------------------------------------------
    # Hash password
    # --------------------------------------------------------

    hashed_password = hash_password(
        request.password
    )


    # --------------------------------------------------------
    # Create user
    # --------------------------------------------------------

    user = User(
        email=request.email,
        password_hash=hashed_password,
        email_verified=False,
        email_verification_token_hash=verification_token_hash,
        email_verification_expires_at=verification_expires_at
    )


    db.add(user)


    # --------------------------------------------------------
    # Create verification URL
    # --------------------------------------------------------

    frontend_url = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173"
    ).rstrip("/")


    verification_url = (
        f"{frontend_url}/verify-email"
        f"?token={verification_token}"
    )


    # --------------------------------------------------------
    # Send verification email
    # --------------------------------------------------------

    try:

        send_verification_email(
            request.email,
            verification_url
        )

    except Exception as e:

        db.rollback()

        print(
            "Email sending failed:",
            str(e)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to send verification email. Please try again."
        )


    # --------------------------------------------------------
    # Save user
    # --------------------------------------------------------

    db.commit()

    db.refresh(user)


    return {
        "message":
            "Registration successful. Please check your email to verify your account.",

        "user_id":
            user.id,

        "email":
            user.email
    }


# ============================================================
# Verify Email
# ============================================================

@router.post("/verify-email")
def verify_email(
    request: VerifyEmailRequest,
    db: Session = Depends(get_db)
):

    token_hash = hashlib.sha256(
        request.token.encode("utf-8")
    ).hexdigest()


    user = db.query(
        User
    ).filter(
        User.email_verification_token_hash == token_hash
    ).first()


    if not user:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification link."
        )


    # --------------------------------------------------------
    # Check expiration
    # --------------------------------------------------------

    if (
        not user.email_verification_expires_at
        or user.email_verification_expires_at < datetime.utcnow()
    ):

        raise HTTPException(
            status_code=400,
            detail="Verification link has expired."
        )


    # --------------------------------------------------------
    # Verify email
    # --------------------------------------------------------

    user.email_verified = True


    # --------------------------------------------------------
    # Invalidate verification token
    # --------------------------------------------------------

    user.email_verification_token_hash = None

    user.email_verification_expires_at = None


    db.commit()


    return {
        "message":
            "Email verified successfully."
    }


# ============================================================
# Forgot Password
# ============================================================

@router.post("/forgot-password")
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):

    # Always return the same response so the endpoint does not
    # reveal whether an email address is registered.
    generic_message = (
        "If an account with that email exists, "
        "a password reset link has been sent."
    )

    user = db.query(
        User
    ).filter(
        User.email == request.email
    ).first()

    if not user:
        return {
            "message": generic_message
        }

    # --------------------------------------------------------
    # Generate secure password reset token
    # --------------------------------------------------------

    reset_token = secrets.token_urlsafe(32)

    reset_token_hash = hashlib.sha256(
        reset_token.encode("utf-8")
    ).hexdigest()

    reset_expires_at = (
        datetime.utcnow() + timedelta(minutes=30)
    )

    user.password_reset_token_hash = reset_token_hash
    user.password_reset_expires_at = reset_expires_at

    # --------------------------------------------------------
    # Create password reset URL
    # --------------------------------------------------------

    frontend_url = os.getenv(
        "FRONTEND_URL",
        "http://localhost:5173"
    ).rstrip("/")

    reset_url = (
        f"{frontend_url}/reset-password"
        f"?token={reset_token}"
    )

    # --------------------------------------------------------
    # Send password reset email
    # --------------------------------------------------------

    try:

        send_password_reset_email(
            request.email,
            reset_url
        )

    except Exception as e:

        db.rollback()

        print(
            "Password reset email sending failed:",
            str(e)
        )

        # Do not expose SMTP/server details to the client.
        raise HTTPException(
            status_code=500,
            detail="Unable to send password reset email. Please try again."
        )

    # --------------------------------------------------------
    # Save reset token
    # --------------------------------------------------------

    db.commit()

    return {
        "message": generic_message
    }


# ============================================================
# Reset Password
# ============================================================

@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Validate new password
    # --------------------------------------------------------

    if len(request.new_password) < 6:

        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 6 characters."
        )

    if len(request.new_password.encode("utf-8")) > 72:

        raise HTTPException(
            status_code=400,
            detail="Password must be 72 bytes or fewer."
        )

    # --------------------------------------------------------
    # Hash reset token
    # --------------------------------------------------------

    token_hash = hashlib.sha256(
        request.token.encode("utf-8")
    ).hexdigest()

    user = db.query(
        User
    ).filter(
        User.password_reset_token_hash == token_hash
    ).first()

    if not user:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired password reset link."
        )

    # --------------------------------------------------------
    # Check expiration
    # --------------------------------------------------------

    if (
        not user.password_reset_expires_at
        or user.password_reset_expires_at < datetime.utcnow()
    ):

        raise HTTPException(
            status_code=400,
            detail="Password reset link has expired."
        )

    # --------------------------------------------------------
    # Check password history
    # --------------------------------------------------------
    # Prevent the user from reusing any of their last 5 passwords.
    previous_passwords = (
        db.query(PasswordHistory)
        .filter(PasswordHistory.user_id == user.id)
        .order_by(PasswordHistory.created_at.desc())
        .limit(5)
        .all()
    )

    for previous_password in previous_passwords:
        if verify_password(
            request.new_password,
            previous_password.password_hash
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "You have already used this password. "
                    "Please choose a different password."
                )
            )

    # Also prevent reusing the user's current password.
    if verify_password(
        request.new_password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "You have already used this password. "
                "Please choose a different password."
            )
        )

    # --------------------------------------------------------
    # Save current password in history before changing it
    # --------------------------------------------------------

    old_password_history = PasswordHistory(
        user_id=user.id,
        password_hash=user.password_hash
    )

    db.add(old_password_history)

    # --------------------------------------------------------
    # Update password
    # --------------------------------------------------------

    user.password_hash = hash_password(
        request.new_password
    )

    # --------------------------------------------------------
    # Mark the email as verified
    # --------------------------------------------------------
    # The user proved access to this email address by using the
    # password-reset link sent to that address.
    user.email_verified = True

    # Clear any old email-verification token as well.
    user.email_verification_token_hash = None
    user.email_verification_expires_at = None

    # --------------------------------------------------------
    # Invalidate reset token after successful use
    # --------------------------------------------------------

    user.password_reset_token_hash = None
    user.password_reset_expires_at = None

    db.flush()

    # --------------------------------------------------------
    # Keep only the latest 5 previous passwords
    # --------------------------------------------------------

    all_password_history = (
        db.query(PasswordHistory)
        .filter(PasswordHistory.user_id == user.id)
        .order_by(PasswordHistory.created_at.desc())
        .all()
    )

    for old_password in all_password_history[5:]:
        db.delete(old_password)

    db.commit()

    return {
        "message":
            "Password reset successfully. Please sign in with your new password."
    }


# ============================================================
# Login
# ============================================================

@router.post("/login")
def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):

    user = db.query(
        User
    ).filter(
        User.email == request.email
    ).first()


    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )


    if not verify_password(
        request.password,
        user.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )


    # --------------------------------------------------------
    # Require email verification
    # --------------------------------------------------------

    if not user.email_verified:

        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in."
        )


    token = create_access_token(
        user.id
    )


    return {
        "message":
            "Login successful.",

        "access_token":
            token,

        "token_type":
            "bearer",

        "user_id":
            user.id
    }


# ============================================================
# Google Login
# ============================================================

@router.post("/google")
def google_login(
    request: GoogleLoginRequest,
    db: Session = Depends(get_db)
):

    try:

        # Verify the Google ID token
        google_user = id_token.verify_oauth2_token(
            request.credential,
            requests.Request()
        )

    except ValueError:

        raise HTTPException(
            status_code=401,
            detail="Invalid Google credential."
        )


    # --------------------------------------------------------
    # Get verified Google email
    # --------------------------------------------------------

    email = google_user.get("email")


    if not email:

        raise HTTPException(
            status_code=400,
            detail="Google account email was not provided."
        )


    # --------------------------------------------------------
    # Make sure Google has verified the email
    # --------------------------------------------------------

    if not google_user.get("email_verified", False):

        raise HTTPException(
            status_code=400,
            detail="Google email address is not verified."
        )


    # --------------------------------------------------------
    # Find existing user
    # --------------------------------------------------------

    user = db.query(
        User
    ).filter(
        User.email == email
    ).first()


    # --------------------------------------------------------
    # Create user if this is a new Google account
    # --------------------------------------------------------

    if not user:

        # User.password_hash is currently required by your
        # database model, so create a random unusable password.
        random_password = secrets.token_urlsafe(32)

        hashed_password = hash_password(
            random_password
        )


        user = User(
            email=email,
            password_hash=hashed_password,
            email_verified=True
        )


        db.add(user)

        db.commit()

        db.refresh(user)

    else:

        # Google has already verified this email.
        # Mark the existing account as verified as well.

        if not user.email_verified:

            user.email_verified = True

            user.email_verification_token_hash = None

            user.email_verification_expires_at = None

            db.commit()

            db.refresh(user)


    # --------------------------------------------------------
    # Create your application's JWT
    # --------------------------------------------------------

    token = create_access_token(
        user.id
    )


    return {
        "message":
            "Google login successful.",

        "access_token":
            token,

        "token_type":
            "bearer",

        "user_id":
            user.id,

        "email":
            user.email
    }


# ============================================================
# Current logged-in user
# ============================================================

@router.get("/me")
def get_me(
    current_user=Depends(get_current_user)
):

    return {
        "user_id": current_user.id,
        "email": current_user.email
    }