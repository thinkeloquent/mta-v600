"""
Tests for PriorityQueue

Coverage includes:
- Statement/Branch/Condition coverage
- MC/DC for conditional logic
- Boundary value analysis
- State transition testing
"""

import pytest
import time
from fetch_rate_limiter.queue import PriorityQueue
from fetch_rate_limiter.types import QueuedRequest


def create_request(
    id: str,
    priority: int = 0,
    enqueued_at: float = None,
    deadline: float = None,
) -> QueuedRequest:
    """Helper to create test requests."""
    return QueuedRequest(
        id=id,
        fn=lambda: id,
        priority=priority,
        enqueued_at=enqueued_at if enqueued_at is not None else time.time(),
        deadline=deadline,
        metadata={"id": id},
    )


class TestEnqueue:
    """Tests for enqueue method."""

    def test_add_single_item_to_empty_queue(self):
        queue = PriorityQueue()
        request = create_request("req1")
        queue.enqueue(request)

        assert queue.size == 1
        assert not queue.is_empty()

    def test_maintain_priority_order_higher_first(self):
        queue = PriorityQueue()
        now = time.time()

        queue.enqueue(create_request("low", 0, now))
        queue.enqueue(create_request("high", 10, now))
        queue.enqueue(create_request("medium", 5, now))

        assert queue.dequeue().id == "high"
        assert queue.dequeue().id == "medium"
        assert queue.dequeue().id == "low"

    def test_maintain_fifo_order_for_same_priority(self):
        queue = PriorityQueue()

        queue.enqueue(create_request("first", 5, 1000.0))
        queue.enqueue(create_request("second", 5, 2000.0))
        queue.enqueue(create_request("third", 5, 3000.0))

        assert queue.dequeue().id == "first"
        assert queue.dequeue().id == "second"
        assert queue.dequeue().id == "third"

    def test_handle_negative_priorities(self):
        queue = PriorityQueue()
        now = time.time()

        queue.enqueue(create_request("negative", -5, now))
        queue.enqueue(create_request("zero", 0, now))
        queue.enqueue(create_request("positive", 5, now))

        assert queue.dequeue().id == "positive"
        assert queue.dequeue().id == "zero"
        assert queue.dequeue().id == "negative"

    def test_handle_large_number_of_items(self):
        queue = PriorityQueue()
        count = 1000

        for i in range(count):
            queue.enqueue(create_request(f"req{i}", i % 100, float(i)))

        assert queue.size == count

        last_priority = float("inf")
        while not queue.is_empty():
            item = queue.dequeue()
            assert item.priority <= last_priority
            last_priority = item.priority


class TestDequeue:
    """Tests for dequeue method."""

    def test_return_none_for_empty_queue(self):
        queue = PriorityQueue()
        assert queue.dequeue() is None

    def test_remove_and_return_highest_priority_item(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1", 1))
        queue.enqueue(create_request("req2", 2))

        item = queue.dequeue()
        assert item.id == "req2"
        assert queue.size == 1

    def test_empty_queue_after_dequeuing_all_items(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1", 0))
        queue.dequeue()

        assert queue.is_empty()
        assert queue.size == 0


class TestPeek:
    """Tests for peek method."""

    def test_return_none_for_empty_queue(self):
        queue = PriorityQueue()
        assert queue.peek() is None

    def test_return_highest_priority_without_removing(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1", 1))
        queue.enqueue(create_request("req2", 2))

        assert queue.peek().id == "req2"
        assert queue.size == 2
        assert queue.peek().id == "req2"


class TestIsEmpty:
    """Tests for is_empty method."""

    def test_return_true_for_new_queue(self):
        queue = PriorityQueue()
        assert queue.is_empty()

    def test_return_false_after_adding_item(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1"))
        assert not queue.is_empty()

    def test_return_true_after_removing_all_items(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1"))
        queue.dequeue()
        assert queue.is_empty()


class TestSize:
    """Tests for size property."""

    def test_zero_for_new_queue(self):
        queue = PriorityQueue()
        assert queue.size == 0

    def test_track_additions_correctly(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1"))
        assert queue.size == 1
        queue.enqueue(create_request("req2"))
        assert queue.size == 2

    def test_track_removals_correctly(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1"))
        queue.enqueue(create_request("req2"))
        queue.dequeue()
        assert queue.size == 1


class TestRemoveExpired:
    """Tests for remove_expired method."""

    def test_return_empty_list_when_no_expired_items(self):
        queue = PriorityQueue()
        now = time.time()
        queue.enqueue(create_request("req1", 0, now, now + 10000))

        expired = queue.remove_expired(now)
        assert len(expired) == 0
        assert queue.size == 1

    def test_remove_and_return_expired_items(self):
        queue = PriorityQueue()
        now = time.time()
        queue.enqueue(create_request("expired", 0, now, now - 1000))
        queue.enqueue(create_request("valid", 0, now, now + 10000))

        expired = queue.remove_expired(now)
        assert len(expired) == 1
        assert expired[0].id == "expired"
        assert queue.size == 1

    def test_not_remove_items_without_deadline(self):
        queue = PriorityQueue()
        now = time.time()
        queue.enqueue(create_request("no_deadline", 0, now))
        queue.enqueue(create_request("expired", 0, now, now - 1000))

        expired = queue.remove_expired(now)
        assert len(expired) == 1
        assert queue.size == 1

    def test_handle_boundary_case_deadline_equals_now(self):
        queue = PriorityQueue()
        now = time.time()
        # deadline == now is NOT expired (only deadline < now is expired)
        queue.enqueue(create_request("boundary", 0, now, now))

        expired = queue.remove_expired(now)
        # The implementation uses deadline < now, so deadline == now is not expired
        assert len(expired) == 0

    def test_remove_all_expired_items(self):
        queue = PriorityQueue()
        now = time.time()
        queue.enqueue(create_request("exp1", 0, now, now - 1000))
        queue.enqueue(create_request("exp2", 0, now, now - 500))
        queue.enqueue(create_request("valid", 0, now, now + 1000))

        expired = queue.remove_expired(now)
        assert len(expired) == 2
        assert queue.size == 1


class TestRemoveById:
    """Tests for remove_by_id method."""

    def test_return_none_for_nonexistent_id(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1"))

        assert queue.remove_by_id("nonexistent") is None
        assert queue.size == 1

    def test_remove_and_return_item_by_id(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1"))
        queue.enqueue(create_request("req2"))
        queue.enqueue(create_request("req3"))

        removed = queue.remove_by_id("req2")
        assert removed.id == "req2"
        assert queue.size == 2

    def test_return_none_for_empty_queue(self):
        queue = PriorityQueue()
        assert queue.remove_by_id("any") is None


class TestClear:
    """Tests for clear method."""

    def test_return_empty_list_for_empty_queue(self):
        queue = PriorityQueue()
        assert queue.clear() == []

    def test_remove_and_return_all_items(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1"))
        queue.enqueue(create_request("req2"))
        queue.enqueue(create_request("req3"))

        cleared = queue.clear()
        assert len(cleared) == 3
        assert queue.is_empty()


class TestGetAll:
    """Tests for get_all method."""

    def test_return_empty_list_for_empty_queue(self):
        queue = PriorityQueue()
        assert queue.get_all() == []

    def test_return_all_items_without_modifying_queue(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("req1", 2))
        queue.enqueue(create_request("req2", 1))
        queue.enqueue(create_request("req3", 3))

        all_items = queue.get_all()
        assert len(all_items) == 3
        assert queue.size == 3


class TestStateTransitions:
    """Tests for state transitions."""

    def test_rapid_add_remove_cycles(self):
        queue = PriorityQueue()

        for i in range(100):
            queue.enqueue(create_request(f"req{i}", i % 10))
            if i % 3 == 0:
                queue.dequeue()

        assert queue.size == 100 - 34

    def test_consistency_after_mixed_operations(self):
        queue = PriorityQueue()
        now = time.time()

        queue.enqueue(create_request("req1", 5, now, now + 10000))
        queue.enqueue(create_request("req2", 3, now, now - 1000))
        queue.enqueue(create_request("req3", 7, now))

        queue.remove_by_id("req1")
        queue.remove_expired(now)

        assert queue.size == 1
        assert queue.peek().id == "req3"


class TestBoundaryValueAnalysis:
    """Tests for boundary values."""

    def test_handle_very_large_priority(self):
        queue = PriorityQueue()
        queue.enqueue(create_request("max", 10**9))
        queue.enqueue(create_request("min", -(10**9)))
        queue.enqueue(create_request("zero", 0))

        assert queue.dequeue().id == "max"
        assert queue.dequeue().id == "zero"
        assert queue.dequeue().id == "min"

    def test_handle_edge_timestamps(self):
        queue = PriorityQueue()
        # With same priority, FIFO order is determined by enqueued_at timestamp
        queue.enqueue(create_request("epoch", 0, 0.0))
        queue.enqueue(create_request("future", 0, 10.0**9))

        # epoch has smaller enqueued_at (0.0) so it should come first
        item1 = queue.dequeue()
        item2 = queue.dequeue()
        assert item1.id == "epoch"
        assert item2.id == "future"

    def test_handle_empty_string_id(self):
        queue = PriorityQueue()
        queue.enqueue(create_request(""))
        assert queue.size == 1

    def test_handle_special_characters_in_id(self):
        queue = PriorityQueue()
        special_id = "req:user@domain.com:path/to/resource"
        queue.enqueue(create_request(special_id))
        assert queue.dequeue().id == special_id
