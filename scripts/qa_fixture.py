"""Disposable QA identity and fixtures; run inside the API network, never as an endpoint."""
import base64
import io
import json
import secrets
import sys
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from docx import Document as WordDocument
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Document, User
from app.repositories.documents import DocumentRepository
from app.services.storage import ObjectStorage

storage = ObjectStorage(get_settings())
with SessionLocal() as session:
    if sys.argv[1] == "seed":
        password = secrets.token_urlsafe(24)
        user = User(email=f"browser-qa-{uuid4().hex}@example.com", password_hash=hash_password(password))
        session.add(user)
        session.commit()
        source = io.BytesIO()
        word = WordDocument()
        word.add_paragraph("Quasar verification evidence jane@example.com")
        word.save(source)
        key = f"quarantine/qa-{uuid4().hex}/retry.docx"
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "retry.docx"
            path.write_bytes(source.getvalue())
            storage.upload_file(path, key, mime)
        repository = DocumentRepository(session)
        document = repository.create(
            owner_id=user.id, original_filename="retry.docx", content_type=mime,
            byte_size=len(source.getvalue()), sha256="0" * 64, quarantine_key=key,
        )
        repository.mark_failed(document, "QA fixture: retry required")
        print(json.dumps({"id": str(user.id), "email": user.email, "password": password,
                          "document_id": str(document.id),
                          "file": base64.b64encode(source.getvalue()).decode()}))
    elif sys.argv[1] == "cleanup":
        user = session.get(User, UUID(sys.argv[2]))
        if user is None or not user.email.startswith("browser-qa-"):
            raise ValueError("Not a disposable QA account")
        for document in session.scalars(select(Document).where(Document.owner_id == user.id)):
            for key in (document.storage_key, document.quarantine_key):
                if key:
                    storage.delete(key)
            session.delete(document)
        session.flush()
        session.delete(user)
        session.commit()
