from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.models import User
from app.schemas.user import UserCreate, UserUpdate

class CRUDUser:
    def get(self, db: Session, user_id: UUID) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    def create(self, db: Session, obj_in: UserCreate) -> User:
        hashed_password = get_password_hash(obj_in.password)
        db_obj = User(
            email=obj_in.email,
            hashed_password=hashed_password,
            is_active=obj_in.is_active
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: User, obj_in: UserUpdate) -> User:
        if obj_in.email:
            db_obj.email = obj_in.email
        if obj_in.password:
            db_obj.hashed_password = get_password_hash(obj_in.password)
        if obj_in.is_active is not None:
            db_obj.is_active = obj_in.is_active

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

user = CRUDUser()