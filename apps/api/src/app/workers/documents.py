import logging
import time
from typing import cast
from uuid import UUID, uuid4

from redis import Redis
from redis.exceptions import RedisError, ResponseError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import SessionLocal, engine
from app.models import Document, DocumentStatus
from app.repositories.documents import DocumentRepository
from app.services.documents import DocumentProcessor
from app.services.extraction import DocumentExtractor
from app.services.malware import ClamAvScanner
from app.services.queue import DocumentQueue
from app.services.storage import ObjectStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
GROUP = "document-workers"
CLAIM_IDLE_MS = 60_000


def reconcile(settings: Settings) -> None:
    """Recover committed work even when notification or Redis persistence was lost."""
    with SessionLocal() as session:
        ids = list(session.scalars(select(Document.id).where(
            Document.status.in_([DocumentStatus.QUEUED, DocumentStatus.PROCESSING])
        ).order_by(Document.updated_at).limit(20)))
    for document_id in ids:
        process_message({"document_id": str(document_id)}, settings)


def process_message(payload: dict[str, str], settings: Settings) -> bool:
    """Serialize duplicate deliveries with a connection-scoped PostgreSQL lock."""
    document_id = UUID(payload["document_id"])
    lock_id = int.from_bytes(document_id.bytes[:8], "big", signed=True)
    with engine.connect() as connection:
        acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_id})
        connection.commit()
        if not acquired:
            return False
        try:
            with Session(bind=connection) as session:
                DocumentProcessor(
                    DocumentRepository(session), ObjectStorage(settings),
                    ClamAvScanner(settings), DocumentExtractor(),
                ).process(document_id, resume=True)
            return True
        finally:
            connection.rollback()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
            connection.commit()


def main() -> None:
    settings = get_settings()
    redis = Redis.from_url(
        settings.redis_url, decode_responses=True, socket_connect_timeout=2, socket_timeout=10
    )
    consumer = f"document-worker-{uuid4().hex}"
    cursor = "0-0"
    while True:
        try:
            reconcile(settings)
            try:
                redis.xgroup_create(DocumentQueue.stream, GROUP, id="0", mkstream=True)
            except ResponseError as error:
                if "BUSYGROUP" not in str(error):
                    raise
            claimed = cast(list[object], redis.xautoclaim(
                DocumentQueue.stream, GROUP, consumer, CLAIM_IDLE_MS, start_id=cursor, count=1
            ))
            cursor = str(claimed[0])
            recovered = cast(list[tuple[str, dict[str, str]]], claimed[1])
            messages = cast(
                list[tuple[str, list[tuple[str, dict[str, str]]]]],
                redis.xreadgroup(
                    GROUP, consumer, {DocumentQueue.stream: ">"}, count=1, block=5000
                ),
            )
            if recovered:
                messages.append((DocumentQueue.stream, recovered))
            for _, entries in messages:
                for message_id, payload in entries:
                    try:
                        if process_message(payload, settings):
                            redis.xack(DocumentQueue.stream, GROUP, message_id)
                    except (KeyError, ValueError):
                        logger.error("Discarding malformed queue message %s", message_id)
                        redis.xack(DocumentQueue.stream, GROUP, message_id)
                    except Exception:
                        logger.exception("Processing failed for message %s", message_id)
        except RedisError:
            logger.warning("Redis unavailable; retrying with database reconciliation")
            time.sleep(5)
        except Exception:
            logger.exception("Worker dependency unavailable; retrying")
            time.sleep(5)


if __name__ == "__main__":
    main()
