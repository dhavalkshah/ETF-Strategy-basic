from typing import Optional
from datetime import datetime
import uuid

from pydantic import BaseModel, EmailStr, Field

# Shared properties
class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = True

# Properties to receive via API on creation
class UserCreate(UserBase):
    email: EmailStr
    password: str

# Properties to receive via API on update
class UserUpdate(UserBase):
    password: Optional[str] = None

# Properties shared by models stored in DB
class UserInDBBase(UserBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

# Additional properties to return via API
class UserOut(UserInDBBase): # This is the public facing user schema
    pass

# Additional properties stored in DB but not returned by API
class UserInDB(UserInDBBase):
    hashed_password: str