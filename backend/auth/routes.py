from fastapi import APIRouter, Depends, HTTPException
from backend.auth.dependencies import get_current_user
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import User

from backend.auth.security import (
    hash_password,
    verify_password,
    create_access_token
)


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


    hashed_password = hash_password(
        request.password
    )


    user = User(
        email=request.email,
        password_hash=hashed_password
    )


    db.add(user)

    db.commit()

    db.refresh(user)


    return {
        "message":
            "User registered successfully.",

        "user_id":
            user.id,

        "email":
            user.email
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