"""Authentication schemas."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone_number: str | None = Field(default=None, max_length=30)


class RegisterResponse(BaseModel):
    user_id: str
    email: EmailStr
    is_email_verified: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    id_token: str
