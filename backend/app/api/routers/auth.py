from datetime import datetime, timezone

import secrets
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.schemas import AuthUserSchema, LoginRequest, RegisterRequest, UpdateProfileRequest
from app.database.models import UserModel
from app.database.session import get_db
from app.dependencies import get_current_user
from app.services.auth import (
    clear_session_cookie,
    hash_password,
    set_session_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthUserSchema, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = db.query(UserModel).filter(UserModel.username == username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    user = UserModel(
        id=secrets.token_urlsafe(18),
        username=username,
        password_hash=hash_password(body.password),
        created_at=int(datetime.now(timezone.utc).timestamp() * 1000),
    )
    db.add(user)
    db.commit()
    set_session_cookie(response, user.id)
    return AuthUserSchema(id=user.id, username=user.username)


@router.post("/login", response_model=AuthUserSchema)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    username = body.username.strip().lower()
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    set_session_cookie(response, user.id)
    return AuthUserSchema(id=user.id, username=user.username)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    clear_session_cookie(response)


@router.get("/me", response_model=AuthUserSchema)
def me(current_user: UserModel = Depends(get_current_user)):
    return AuthUserSchema(id=current_user.id, username=current_user.username)


@router.put("/profile", response_model=AuthUserSchema)
def update_profile(
    body: UpdateProfileRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user),
):
    if not verify_password(body.currentPassword, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    next_username = body.username.strip().lower() if body.username is not None else current_user.username
    next_password = body.newPassword if body.newPassword is not None else None

    wants_username_change = next_username != current_user.username
    wants_password_change = bool(next_password)
    if not wants_username_change and not wants_password_change:
        raise HTTPException(status_code=400, detail="No profile changes were provided")

    if wants_username_change:
        if len(next_username) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        existing = db.query(UserModel).filter(UserModel.username == next_username).first()
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=409, detail="Username already exists")
        current_user.username = next_username

    if wants_password_change:
        if len(next_password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
        current_user.password_hash = hash_password(next_password)

    db.commit()
    db.refresh(current_user)
    return AuthUserSchema(id=current_user.id, username=current_user.username)
