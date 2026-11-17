"""Validate administration requests and public responses."""

import re
from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

RoleName = Literal['Administrator', 'Executive', 'Portfolio Leader', 'Engineer', 'Auditor', 'Read Only']
Permission = Literal['view', 'create', 'edit', 'delete', 'export', 'administer']
ObjectIdString = Annotated[str, BeforeValidator(str)]


class UserInput(BaseModel):
    """Accept editable account details without allowing arbitrary fields."""
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)
    role: RoleName
    portfolioAccess: list[str] = Field(default_factory=list, max_length=1000)
    status: Literal['Active', 'Inactive'] = 'Active'
    password: str | None = Field(default=None, min_length=12, max_length=72)

    @field_validator('name')
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Reject whitespace-only account names."""
        value = value.strip()
        if not value:
            raise ValueError('Name is required')
        return value

    @field_validator('email')
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Normalize and validate the account's email address."""
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError('Invalid email address')
        return value

    @field_validator('password')
    @classmethod
    def validate_password(cls, value: str | None) -> str | None:
        """Enforce bcrypt's byte limit."""
        if value is not None and len(value.encode('utf-8')) > 72:
            raise ValueError('Password must not exceed 72 bytes')
        return value


class UserResponse(BaseModel):
    """Expose account administration fields without credentials."""
    model_config = ConfigDict(populate_by_name=True)
    id: ObjectIdString = Field(validation_alias='_id', serialization_alias='id')
    name: str
    email: str
    role: RoleName
    portfolioAccess: list[str]
    status: str
    defaultLandingPage: str
    permissions: list[str] = []


class UserPage(BaseModel):
    """Return a bounded page of users."""
    items: list[UserResponse]
    total: int
    limit: int
    offset: int


class RoleInput(BaseModel):
    """Accept one of the supported roles and its configurable permissions."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: RoleName
    description: str = Field(default='', max_length=500)
    permissions: list[Permission] = Field(max_length=6)

    @field_validator('permissions')
    @classmethod
    def unique_permissions(cls, value: list[str]) -> list[str]:
        """Reject repeated permission names."""
        if len(set(value)) != len(value):
            raise ValueError('Permissions must be unique')
        return value


class RoleResponse(RoleInput):
    """Expose a persisted role."""
    model_config = ConfigDict(populate_by_name=True, extra='ignore')
    id: ObjectIdString = Field(validation_alias='_id', serialization_alias='id')


class RolePage(BaseModel):
    """Return a bounded page of roles."""
    items: list[RoleResponse]
    total: int
    limit: int
    offset: int


class AuditResponse(BaseModel):
    """Expose denormalized, credential-free audit history."""
    model_config = ConfigDict(populate_by_name=True)
    id: ObjectIdString = Field(validation_alias='_id', serialization_alias='id')
    timestamp: datetime
    userId: ObjectIdString | None
    userName: str
    action: str
    entityType: str
    entityId: str | None
    details: str


class AuditPage(BaseModel):
    """Return a bounded page of audit events."""
    items: list[AuditResponse]
    total: int
    limit: int
    offset: int
