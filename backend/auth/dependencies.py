import os

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import User


security = HTTPBearer()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

ALGORITHM = "HS256"


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):

    token = credentials.credentials

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get(
            "user_id"
        )

        if user_id is None:

            raise HTTPException(
                status_code=401,
                detail="Invalid token."
            )

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token."
        )


    user = db.query(
        User
    ).filter(
        User.id == user_id
    ).first()


    if user is None:

        raise HTTPException(
            status_code=401,
            detail="User not found."
        )


    return user