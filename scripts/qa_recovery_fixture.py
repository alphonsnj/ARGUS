"""Synthetic recovery fixture. Only invoked in isolated drill networks."""

import hashlib
import sys

from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Document, DocumentEntity, DocumentStatus, User
from app.services.storage import ObjectStorage

storage = ObjectStorage(get_settings())
payload = b"Synthetic recovery evidence\x00\xff\n"
keys = ["evidence/recovery.bin", "quarantine/nested folder/recovery evidence.bin"]
with SessionLocal() as session:
    if sys.argv[1] == "seed":
        user = User(email="restore-drill@example.com", password_hash="disabled-test-account")
        session.add(user)
        session.flush()
        storage.ensure_bucket()
        for i, key in enumerate(keys):
            storage._client.put_object(
                Bucket=storage._bucket,
                Key=key,
                Body=payload,
                ContentType="application/octet-stream",
                Metadata={"drill": "synthetic"},
            )
            session.add(
                Document(
                    owner_id=user.id,
                    original_filename=f"recovery-{i}.bin",
                    content_type="application/octet-stream",
                    byte_size=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest(),
                    status=DocumentStatus.READY if i == 0 else DocumentStatus.FAILED,
                    storage_key=key if i == 0 else None,
                    quarantine_key=key if i == 1 else None,
                    extracted_text="Quasar recovery evidence" if i == 0 else None,
                    extracted_metadata={"source": "drill"},
                    entities=[
                        DocumentEntity(
                            kind="email",
                            value="restore-drill@example.com",
                            normalized_value="restore-drill@example.com",
                        )
                    ],
                )
            )
        session.commit()
        session.execute(
            text("UPDATE documents SET search_vector = to_tsvector('english', extracted_text)")
        )
        session.commit()
    elif sys.argv[1] == "verify":
        users = list(session.scalars(select(User)))
        documents = list(session.scalars(select(Document)))
        assert len(users) == 1 and users[0].email == "restore-drill@example.com"
        assert len(documents) == 2
        for document in documents:
            assert document.owner_id == users[0].id
            assert document.extracted_metadata == {"source": "drill"}
            assert len(document.entities) == 1
            key = document.storage_key or document.quarantine_key
            result = storage._client.get_object(Bucket=storage._bucket, Key=key)
            assert result["Body"].read() == payload
            assert result["ContentType"] == "application/octet-stream"
            assert result["Metadata"] == {"drill": "synthetic"}
        assert (
            session.scalar(
                text(
                    "SELECT count(*) FROM documents WHERE "
                    "search_vector @@ plainto_tsquery('english', 'Quasar')"
                )
            )
            == 1
        )
        assert session.scalar(text("SELECT version_num FROM alembic_version"))
        print(
            "PASS restored schema, users, documents, foreign keys, entities, "
            "search and object bytes/metadata"
        )
    else:
        raise RuntimeError("Unknown fixture action")
