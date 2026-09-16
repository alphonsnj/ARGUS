"""Recover a dead consumer's pending job in an isolated Redis stream."""
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from docx import Document as WordDocument
from redis import Redis
from sqlalchemy import text

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models import Document, DocumentStatus, User
from app.repositories.documents import DocumentRepository
from app.services.storage import ObjectStorage
from app.workers.documents import process_message


@pytest.mark.skipif(os.environ.get("ARGUS_LIVE_TEST") != "1", reason="Requires Compose stack")
def test_recovers_interrupted_processing(tmp_path: Path) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    stream = f"argus:test-recovery:{uuid4().hex}"
    group = "test-workers"
    storage = ObjectStorage(settings)
    source_key = f"quarantine/test-{uuid4().hex}/recovery.docx"
    source = tmp_path / "recovery.docx"
    word = WordDocument()
    word.add_paragraph("Recoverable evidence from interrupted worker.")
    word.save(source)
    process = None
    document_id = None
    user_id = None
    try:
        storage.upload_file(
            source, source_key,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        with SessionLocal() as session:
            user = User(
                email=f"recovery-{uuid4().hex}@example.com",
                password_hash=hash_password(uuid4().hex),
            )
            session.add(user)
            session.commit()
            user_id = user.id
            repository = DocumentRepository(session)
            document = repository.create(
                owner_id=user_id, original_filename="recovery.docx",
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                byte_size=source.stat().st_size, sha256="0" * 64, quarantine_key=source_key,
            )
            document_id = document.id
            repository.mark_processing(document)
        # A slow but live worker must not be processed concurrently after a claim.
        lock_id = int.from_bytes(document_id.bytes[:8], "big", signed=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": lock_id})
            connection.commit()
            try:
                assert process_message({"document_id": str(document_id)}, settings) is False
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                connection.commit()
        redis.xgroup_create(stream, group, id="0", mkstream=True)
        message_id = redis.xadd(stream, {"document_id": str(document_id)})
        redis.xreadgroup(group, "dead-worker", {stream: ">"}, count=1)
        redis.xclaim(stream, group, "dead-worker", 0, [message_id], idle=120_000)
        process = subprocess.Popen([
            sys.executable, "-c",
            "from app.workers import documents as worker; "
            f"worker.DocumentQueue.stream={stream!r}; worker.GROUP={group!r}; worker.main()",
        ], env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            with SessionLocal() as session:
                document = session.get(Document, document_id)
                if (document.status == DocumentStatus.READY
                        and redis.xpending(stream, group)["pending"] == 0):
                    break
            time.sleep(1)
        else:
            pytest.fail("Interrupted document was not recovered and acknowledged")
    finally:
        if process:
            process.terminate()
            process.wait(timeout=10)
        redis.delete(stream)
        storage.delete(source_key)
        with SessionLocal() as session:
            if document_id:
                document = session.get(Document, document_id)
                if document:
                    if document.storage_key:
                        storage.delete(document.storage_key)
                    session.delete(document)
                    session.flush()
            if user_id:
                user = session.get(User, user_id)
                if user:
                    session.delete(user)
            session.commit()
