import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.db.session import SessionLocal
from app.models import Document, DocumentStatus, User
from app.repositories.documents import DocumentRepository


@pytest.mark.skipif(os.environ.get("ARGUS_LIVE_TEST") != "1", reason="Requires PostgreSQL")
def test_concurrent_upload_capacity_is_serialized() -> None:
    with SessionLocal() as session:
        user = User(email=f"quota-{uuid4().hex}@example.com", password_hash="disabled")
        session.add(user)
        session.commit()
        user_id = user.id
    barrier = Barrier(2)

    def reserve() -> bool:
        with SessionLocal() as session:
            barrier.wait(timeout=10)
            accepted = DocumentRepository(session).reserve_capacity(user_id, 10, 10, 1)
            if accepted:
                session.add(Document(
                    owner_id=user_id, original_filename="quota-test.pdf",
                    content_type="application/pdf", byte_size=10, sha256="0" * 64,
                    status=DocumentStatus.FAILED,
                ))
                session.commit()
            return accepted

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: reserve(), range(2)))
        assert sorted(results) == [False, True]
    finally:
        with SessionLocal() as session:
            session.execute(delete(Document).where(Document.owner_id == user_id))
            session.execute(delete(User).where(User.id == user_id))
            session.commit()
