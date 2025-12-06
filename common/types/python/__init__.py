"""
Common Python types for MTA-v600.

This module contains shared type definitions used across FastAPI applications.
"""

from typing import Any, Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Standard API response wrapper."""

    success: bool
    data: Optional[T] = None
    error: Optional[dict] = None
    meta: Optional[dict] = None


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str
    message: str
    details: Optional[Any] = None


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int


__all__ = ["ApiResponse", "ErrorDetail", "PaginatedResponse"]
