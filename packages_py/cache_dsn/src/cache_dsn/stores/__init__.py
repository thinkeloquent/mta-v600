"""
DNS cache store implementations
"""
from .memory import MemoryStore, create_memory_store

__all__ = [
    "MemoryStore",
    "create_memory_store",
]
