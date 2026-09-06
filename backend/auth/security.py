import os

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from passlib.context import CryptContext

from jose import jwt


# ============================================================
# Load environment variables
# ============================================================

load_dotenv()


# ============================================================
# JWT configuration
# ============================================================

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 60


if not SECRET_KEY:

    raise ValueError(
        "JWT_SECRET_KEY is not configured in .env"
    )


# ============================================================
# Password hashing
# ============================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# ============================================================
# Hash password
# ============================================================

def hash_password(password: str):

    # bcrypt supports a maximum of 72 bytes
    password_bytes = password.encode("utf-8")

    if len(password_bytes) > 72:

        raise ValueError(
            "Password cannot be longer than 72 bytes."
        )

    return pwd_context.hash(password)


# ============================================================
# Verify password
# ============================================================

def verify_password(
    plain_password: str,
    hashed_password: str
):

    password_bytes = plain_password.encode("utf-8")

    if len(password_bytes) > 72:

        return False

    return pwd_context.verify(
        plain_password,
        hashed_password
    )


# ============================================================
# Create JWT access token
# ============================================================

def create_access_token(
    user_id: int
):

    now = datetime.now(
        timezone.utc
    )

    expire = (
        now
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {

        "user_id":
            user_id,

        "iat":
            now,

        "exp":
            expire
    }

    token = jwt.encode(

        payload,

        SECRET_KEY,

        algorithm=ALGORITHM
    )

    return token