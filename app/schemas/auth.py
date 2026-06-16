"""Authentication schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.user import UserPrivateResponse


class RegisterRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "james.harrison@example.com",
            "password": "SecurePass1!",
        }
    })

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class RegisterResponse(BaseModel):
    user_id: str
    email: EmailStr
    is_email_verified: bool


class LoginRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "james.harrison@example.com",
            "password": "SecurePass1!",
        }
    })

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None


class AuthTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPrivateResponse


class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "james.harrison@example.com",
            "token": "483921",
        }
    })

    email: EmailStr
    token: str = Field(min_length=6, max_length=6)


class ResendOTPRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"email": "james.harrison@example.com"}
    })

    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"email": "james.harrison@example.com"}
    })

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "james.harrison@example.com",
            "token": "739204",
            "new_password": "NewSecurePass2!",
        }
    })

    email: EmailStr
    token: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class GoogleAuthRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjFlOWdkay4uLiJ9..."}
    })

    id_token: str


class GoogleMobileAuthRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {"id_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjFlOWdkay4uLiJ9..."}
    })

    id_token: str
