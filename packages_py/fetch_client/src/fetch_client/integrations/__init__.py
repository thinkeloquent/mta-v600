"""
Framework integrations for fetch_client.
"""
from .fastapi import (
    FetchClientService,
    create_lifespan,
    get_client,
)

__all__ = [
    "FetchClientService",
    "create_lifespan",
    "get_client",
]
