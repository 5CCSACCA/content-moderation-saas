import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from .models import UserRole


class UserRegister(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v):
        # Prevents Test@Example.com and test@example.com being treated
        # as different accounts — emails are stored and matched in
        # lowercase consistently.
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_has_letter_and_number(cls, v):
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v):
        # Must match the same normalization used at registration, so a
        # user who registered with mixed-case input can still log in
        # regardless of how they type their email this time.
        return v.lower()


class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"