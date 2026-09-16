import logging
from uuid import UUID

from redis import Redis
from redis.exceptions import RedisError

from app.core.config import Settings


class DocumentQueue:
    stream = "argus:document-ingestion"

    def __init__(self, settings: Settings) -> None:
        self._redis = Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )

    def enqueue(self, document_id: UUID) -> None:
        try:
            self._redis.xadd(self.stream, {"document_id": str(document_id)})
        except RedisError:
            # The committed queued row is durable; the worker reconciles it without Redis.
            logging.getLogger(__name__).warning("Queue unavailable; database recovery scheduled")
