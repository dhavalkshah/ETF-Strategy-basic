from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session
from jose import jwt

from app.core.config import settings
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.crud.user import user as crud_user
from app.schemas.user import UserCreate
from app.db.models import User

class AuthService:
    def authenticate(self, db: Session, email: str, password: str) -> Optional[User]:
        user = crud_user.get_by_email(db, email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_user(self, db: Session, user_in: UserCreate) -> User:
        return crud_user.create(db, obj_in=user_in)

    def create_token_for_user(self, user: User) -> str:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return create_access_token(
            data={"sub": str(user.id)}, expires_delta=access_token_expires
        )

    def get_current_user(self, db: Session, token: str) -> Optional[User]:
        payload = decode_access_token(token)
        if payload is None:
            return None
        user_id = payload.get("sub")
        if user_id is None:
            return None
        user = crud_user.get(db, user_id=user_id)
        return user

auth_service = AuthService()