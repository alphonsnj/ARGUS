"""Opt-in smoke test against the running Compose stack, using disposable records."""
import io
import os
import secrets
import time
from uuid import uuid4

import httpx
import pytest
from docx import Document as WordDocument
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Document, User
from app.services.storage import ObjectStorage


@pytest.mark.skipif(os.environ.get("ARGUS_LIVE_TEST") != "1", reason="Requires Compose stack")
@pytest.mark.parametrize("format_name", ["docx", "png", "pdf"])
def test_upload_scan_extract_search(format_name: str) -> None:
    email = f"smoke-{uuid4().hex}@example.com"
    password = secrets.token_urlsafe(24)
    with SessionLocal() as session:
        user = User(email=email, password_hash=hash_password(password), is_active=True)
        session.add(user)
        session.commit()
        user_id = user.id
    try:
        with httpx.Client(base_url="http://api:8000/api/v1", timeout=30) as client:
            login = client.post("/auth/token", json={"email": email, "password": password})
            assert login.status_code == 200
            client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            source = io.BytesIO()
            content = "Quasar verification evidence. Contact jane@example.com."
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if format_name == "docx":
                word = WordDocument()
                word.add_paragraph(content)
                word.save(source)
            else:
                picture = Image.new("RGB", (1800, 300), "white")
                ImageDraw.Draw(picture).text(
                    (40, 80), content, font=ImageFont.load_default(size=40), fill="black"
                )
                picture.save(source, format=format_name.upper())
                content_type = "image/png" if format_name == "png" else "application/pdf"
            upload = client.post("/documents", files={"file": (
                f"smoke.{format_name}", source.getvalue(), content_type,
            )})
            assert upload.status_code == 202, upload.text
            document_id = upload.json()["id"]
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                record = client.get(f"/documents/{document_id}").json()
                if record["status"] in {"ready", "failed", "rejected"}:
                    break
                time.sleep(1)
            assert record["status"] == "ready", record
            assert record["extracted_metadata"]["emails"] == ["jane@example.com"]
            found = client.get("/documents", params={"query": "Quasar"})
            assert found.status_code == 200
            assert document_id in [item["id"] for item in found.json()]
    finally:
        with SessionLocal() as session:
            storage = ObjectStorage(get_settings())
            for document in session.scalars(select(Document).where(Document.owner_id == user_id)):
                for key in (document.storage_key, document.quarantine_key):
                    if key:
                        storage.delete(key)
                session.delete(document)
            session.flush()
            user = session.get(User, user_id)
            if user:
                session.delete(user)
            session.commit()
