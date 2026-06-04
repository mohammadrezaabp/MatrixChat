from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import SESSION_COOKIE_NAME
from app.database.models import UserModel
from app.database.session import get_db
from app.services.auth import parse_session_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> UserModel:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = parse_session_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    user = db.get(UserModel, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return user
