import os
from collections.abc import Iterator
from unittest.mock import Mock
from uuid import uuid4

import pytest
from redis import Redis

from app.core.config import get_settings
from app.services.queue_retention import trim_completed


def test_disabled_retention_does_not_contact_redis() -> None:
    client = Mock()
    assert trim_completed(client, "unused", 0) == 0
    client.eval.assert_not_called()


@pytest.fixture
def queue() -> Iterator[tuple[Redis, str]]:
    if os.environ.get("ARGUS_REDIS_TEST") != "1" and os.environ.get("ARGUS_LIVE_TEST") != "1":
        pytest.skip("Requires Redis")
    client = Redis.from_url(get_settings().redis_url, decode_responses=True)
    stream = f"argus:test-retention:{uuid4().hex}"
    try:
        yield client, stream
    finally:
        client.delete(stream)  # Only the unique synthetic stream created by this test.
        client.close()


def seed(client: Redis, stream: str) -> list[str]:
    ids = [f"{i}-0" for i in range(1, 601)]
    with client.pipeline() as pipeline:
        for entry in ids:
            pipeline.xadd(stream, {"document_id": "synthetic"}, id=entry)
        pipeline.execute()
    return ids


def delivered(client: Redis, stream: str, group: str, count: int = 600) -> None:
    client.xgroup_create(stream, group, id="0")
    client.xreadgroup(group, "test-consumer", {stream: ">"}, count=count)


def test_missing_stream_and_no_groups_are_preserved(queue: tuple[Redis, str]) -> None:
    client, stream = queue
    assert trim_completed(client, stream, 86400) == 0
    seed(client, stream)
    assert trim_completed(client, stream, 86400) == 0
    assert client.xlen(stream) == 600


def test_only_old_acknowledged_prefix_is_trimmed(queue: tuple[Redis, str]) -> None:
    client, stream = queue
    ids = seed(client, stream)
    delivered(client, stream, "workers")
    client.xack(stream, "workers", *ids)
    recent = client.xadd(stream, {"document_id": "recent"})
    assert trim_completed(client, stream, 86400) > 0
    assert client.xrange(stream, min=recent, max=recent)
    assert client.xrange(stream, min=ids[-1], max=ids[-1])
    assert client.xpending(stream, "workers")["pending"] == 0


def test_pending_messages_survive_and_can_be_claimed(queue: tuple[Redis, str]) -> None:
    client, stream = queue
    ids = seed(client, stream)
    delivered(client, stream, "workers")
    client.xack(stream, "workers", *ids[:200], *ids[201:])
    assert trim_completed(client, stream, 86400) > 0
    assert client.xrange(stream, min=ids[200], max=ids[200])
    reclaimed = client.xautoclaim(stream, "workers", "replacement", 0, count=600)
    assert reclaimed[1][0][0] == ids[200]


def test_all_groups_and_undelivered_messages_are_protected(queue: tuple[Redis, str]) -> None:
    client, stream = queue
    ids = seed(client, stream)
    delivered(client, stream, "fast")
    client.xack(stream, "fast", *ids)
    delivered(client, stream, "slow", 200)
    client.xack(stream, "slow", *ids[:200])
    assert trim_completed(client, stream, 86400) > 0
    # The slow group's boundary and everything it has not read remain intact.
    assert len(client.xrange(stream, min=ids[199])) == 401
    unread = client.xreadgroup("slow", "test-consumer", {stream: ">"}, count=600)
    assert len(unread[0][1]) == 400


def test_unstarted_group_prevents_trimming(queue: tuple[Redis, str]) -> None:
    client, stream = queue
    ids = seed(client, stream)
    delivered(client, stream, "fast")
    client.xack(stream, "fast", *ids)
    client.xgroup_create(stream, "unstarted", id="0")
    assert trim_completed(client, stream, 86400) == 0
    assert client.xlen(stream) == 600


def test_recent_acknowledged_history_is_retained(queue: tuple[Redis, str]) -> None:
    client, stream = queue
    ids = [client.xadd(stream, {"document_id": "recent"}) for _ in range(600)]
    delivered(client, stream, "workers")
    client.xack(stream, "workers", *ids)
    assert trim_completed(client, stream, 86400) == 0
    assert client.xlen(stream) == 600
