from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import APIResponse
from app.services.auth_service import (
    create_session_token,
    ensure_auth_schema,
    get_user_by_email,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


@router.post("/login", response_model=APIResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    ensure_auth_schema()
    user = get_user_by_email(db, payload.email)

    if not user or user.get("status") != "active" or not verify_password(payload.password, str(user.get("password_hash", ""))):
        raise HTTPException(status_code=401, detail="invalid email or password")

    token = create_session_token(
        user_id=int(user["id"]),
        email=str(user["email"]),
        role=str(user.get("role") or "admin"),
    )
    return APIResponse(
        data={
            "token": token,
            "user": {
                "id": int(user["id"]),
                "email": str(user["email"]),
                "role": str(user.get("role") or "admin"),
            },
        }
    )
