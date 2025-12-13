"""
SQLAlchemy 2.0 base types and mixins.

Provides DeclarativeBase for models and common mixins.
Uses Mapped[] and mapped_column() for modern type annotations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


# Type aliases for common column types
str_50 = Annotated[str, mapped_column(String(50))]
str_100 = Annotated[str, mapped_column(String(100))]
str_255 = Annotated[str, mapped_column(String(255))]
str_500 = Annotated[str, mapped_column(String(500))]


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 declarative base class.

    All models should inherit from this class.

    Example:
        class User(Base):
            __tablename__ = "users"

            id: Mapped[int] = mapped_column(primary_key=True)
            email: Mapped[str] = mapped_column(unique=True, index=True)
            is_active: Mapped[bool] = mapped_column(default=True)
    """

    # Type annotation map for common types
    type_annotation_map = {
        datetime: DateTime(timezone=True),
    }


class TimestampMixin:
    """
    Mixin that adds created_at and updated_at columns.

    Example:
        class User(Base, TimestampMixin):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """
    Mixin for soft delete support.

    Example:
        class User(Base, SoftDeleteMixin):
            __tablename__ = "users"
            id: Mapped[int] = mapped_column(primary_key=True)
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    is_deleted: Mapped[bool] = mapped_column(default=False)


class UUIDPrimaryKeyMixin:
    """
    Mixin that uses UUID as primary key.

    Example:
        class User(Base, UUIDPrimaryKeyMixin):
            __tablename__ = "users"
            email: Mapped[str] = mapped_column(unique=True)
    """

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )


class IntPrimaryKeyMixin:
    """
    Mixin that uses auto-incrementing integer as primary key.

    Example:
        class User(Base, IntPrimaryKeyMixin):
            __tablename__ = "users"
            email: Mapped[str] = mapped_column(unique=True)
    """

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class TableNameMixin:
    """
    Mixin that automatically generates table name from class name.

    Converts CamelCase to snake_case and adds 's' suffix.

    Example:
        class UserProfile(Base, TableNameMixin):
            # __tablename__ will be "user_profiles"
            id: Mapped[int] = mapped_column(primary_key=True)
    """

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        import re

        # Convert CamelCase to snake_case
        name = re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()
        # Add 's' suffix for plural
        if name.endswith("s") or name.endswith("x") or name.endswith("z"):
            return name + "es"
        if name.endswith("y"):
            return name[:-1] + "ies"
        return name + "s"


# Common type aliases for mapped columns
IntPK = Annotated[int, mapped_column(primary_key=True)]
UUIDPK = Annotated[UUID, mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)]


def create_base_model(**kwargs: Any) -> type[Base]:
    """
    Factory function to create a custom base model.

    Useful for creating separate bases for different schemas.

    Args:
        **kwargs: Additional attributes to add to the base class.

    Returns:
        A new Base class with custom attributes.
    """

    class CustomBase(DeclarativeBase):
        pass

    for key, value in kwargs.items():
        setattr(CustomBase, key, value)

    return CustomBase
