"""
Priority queue implementation for rate limiter
"""
import heapq
from typing import TypeVar, Generic, Optional
from dataclasses import dataclass, field
from .types import QueuedRequest

T = TypeVar("T")


@dataclass(order=True)
class PriorityItem(Generic[T]):
    """Wrapper for priority queue items with proper ordering"""

    priority: int = field(compare=True)
    """Negative priority (for max-heap behavior)"""

    enqueued_at: float = field(compare=True)
    """Enqueue timestamp for FIFO within same priority"""

    request: QueuedRequest[T] = field(compare=False)
    """The actual request"""


class PriorityQueue(Generic[T]):
    """
    Priority queue that orders requests by priority (higher first)
    and enqueue time (FIFO for same priority).
    """

    def __init__(self) -> None:
        self._items: list[PriorityItem[T]] = []
        self._removed: set[str] = set()  # Track removed request IDs

    def enqueue(self, request: QueuedRequest[T]) -> None:
        """
        Add a request to the queue.

        Args:
            request: The request to enqueue
        """
        # Use negative priority for max-heap behavior (higher priority first)
        item = PriorityItem(
            priority=-request.priority,
            enqueued_at=request.enqueued_at,
            request=request,
        )
        heapq.heappush(self._items, item)

    def dequeue(self) -> Optional[QueuedRequest[T]]:
        """
        Remove and return the highest priority request.

        Returns:
            The highest priority request, or None if empty
        """
        while self._items:
            item = heapq.heappop(self._items)
            if item.request.id not in self._removed:
                return item.request
            self._removed.discard(item.request.id)
        return None

    def peek(self) -> Optional[QueuedRequest[T]]:
        """
        Peek at the highest priority request without removing it.

        Returns:
            The highest priority request, or None if empty
        """
        # Skip removed items
        while self._items and self._items[0].request.id in self._removed:
            heapq.heappop(self._items)
            self._removed.discard(self._items[0].request.id if self._items else "")

        if self._items:
            return self._items[0].request
        return None

    def is_empty(self) -> bool:
        """Check if the queue is empty"""
        # Clean up removed items
        while self._items and self._items[0].request.id in self._removed:
            heapq.heappop(self._items)

        return len(self._items) == 0

    @property
    def size(self) -> int:
        """Get the current queue size (excluding removed items)"""
        return len(self._items) - len(self._removed)

    def remove_expired(self, now: float) -> list[QueuedRequest[T]]:
        """
        Remove all expired requests from the queue.

        Args:
            now: Current timestamp

        Returns:
            List of expired requests
        """
        expired: list[QueuedRequest[T]] = []
        for item in self._items:
            if item.request.id not in self._removed:
                if item.request.deadline and item.request.deadline < now:
                    expired.append(item.request)
                    self._removed.add(item.request.id)
        return expired

    def remove_by_id(self, request_id: str) -> Optional[QueuedRequest[T]]:
        """
        Remove a specific request by ID.

        Args:
            request_id: The request ID to remove

        Returns:
            The removed request, or None if not found
        """
        for item in self._items:
            if item.request.id == request_id and request_id not in self._removed:
                self._removed.add(request_id)
                return item.request
        return None

    def clear(self) -> list[QueuedRequest[T]]:
        """
        Clear all items from the queue.

        Returns:
            List of all removed requests
        """
        items = [
            item.request
            for item in self._items
            if item.request.id not in self._removed
        ]
        self._items.clear()
        self._removed.clear()
        return items

    def get_all(self) -> list[QueuedRequest[T]]:
        """Get all items in the queue (for debugging/monitoring)"""
        return [
            item.request
            for item in self._items
            if item.request.id not in self._removed
        ]
