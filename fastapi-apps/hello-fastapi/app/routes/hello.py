"""Hello API routes."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HelloResponse(BaseModel):
    """Hello endpoint response."""

    message: str
    timestamp: str


class EchoResponse(BaseModel):
    """Echo endpoint response."""

    echo: dict[str, Any]
    receivedAt: str


class ApiInfoResponse(BaseModel):
    """API info response."""

    name: str
    version: str
    status: str
    timestamp: str


@router.get("", response_model=ApiInfoResponse)
async def get_api_info() -> ApiInfoResponse:
    """Get API information and health status."""
    return ApiInfoResponse(
        name="hello-fastapi",
        version="1.0.0",
        status="healthy",
        timestamp=datetime.now().isoformat(),
    )


@router.get("/hello", response_model=HelloResponse)
async def hello(name: str = "World") -> HelloResponse:
    """
    Say hello to someone.

    Args:
        name: The name to greet. Defaults to "World".

    Returns:
        A greeting message with timestamp.
    """
    return HelloResponse(
        message=f"Hello, {name}!",
        timestamp=datetime.now().isoformat(),
    )


@router.post("/echo", response_model=EchoResponse)
async def echo(body: dict[str, Any]) -> EchoResponse:
    """
    Echo back the request body.

    Args:
        body: Any JSON object to echo back.

    Returns:
        The echoed body with a received timestamp.
    """
    return EchoResponse(
        echo=body,
        receivedAt=datetime.now().isoformat(),
    )
