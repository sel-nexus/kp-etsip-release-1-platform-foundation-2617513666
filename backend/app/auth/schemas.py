"""Validate the public identity and profile API contracts."""

from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

ObjectIdString = Annotated[str, BeforeValidator(str)]
LandingPage = Literal["dashboard", "applications"]


class LoginRequest(BaseModel):
    """Accept local credentials without returning them."""
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=72)

    @field_validator("password")
    @classmethod
    def password_bytes(cls, value: str) -> str:
        """Reject inputs bcrypt cannot safely represent."""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        return value


class UserResponse(BaseModel):
    """Expose current account details but never credential material."""
    model_config = ConfigDict(populate_by_name=True)
    id: ObjectIdString = Field(validation_alias="_id", serialization_alias="id")
    name: str
    email: str
    role: str
    portfolioAccess: list[str]
    status: str
    defaultLandingPage: LandingPage
    permissions: list[str]


class LoginResponse(BaseModel):
    """Return the issued token and current user."""
    token: str
    user: UserResponse


class ProfileUpdate(BaseModel):
    """Accept the user's own landing preference."""
    defaultLandingPage: LandingPage


class PasswordUpdate(BaseModel):
    """Require the current password and a bounded replacement."""
    currentPassword: str = Field(min_length=1, max_length=72)
    newPassword: str = Field(min_length=12, max_length=72)

    @field_validator("currentPassword", "newPassword")
    @classmethod
    def password_bytes(cls, value: str) -> str:
        """Enforce bcrypt's byte limit for Unicode credentials."""
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes")
        return value
