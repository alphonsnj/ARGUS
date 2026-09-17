import io
import os
import secrets
import time
import zipfile
from uuid import uuid4

import httpx
import pytest
from docx import Document as WordDocument
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Document, User
from app.services.storage import ObjectStorage

pytestmark = pytest.mark.skipif(
    os.environ.get("ARGUS_LIVE_TEST") != "1", reason="Requires Compose stack"
)


def test_malware_isolation_and_logout() -> None:
    user_ids = []
    clients = []
    source = io.BytesIO()
    word = WordDocument()
    word.add_paragraph("Private quasar evidence jane@example.com")
    word.save(source)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    try:
        for _ in range(2):
            password = secrets.token_urlsafe(24)
            email = f"security-{uuid4().hex}@example.com"
            with SessionLocal() as session:
                user = User(email=email, password_hash=hash_password(password))
                session.add(user)
                session.commit()
                user_ids.append(user.id)
            client = httpx.Client(base_url="http://api:8000/api/v1", timeout=30)
            clients.append(client)
            login = client.post("/auth/token", json={"email": email, "password": password})
            assert login.status_code == 200
            client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
        owner, stranger = clients
        response = owner.post("/documents", files={
            "file": ("private.docx", source.getvalue(), mime)
        })
        assert response.status_code == 202
        document_id = response.json()["id"]
        assert stranger.get(f"/documents/{document_id}").status_code == 404
        assert stranger.post(f"/documents/{document_id}/retry").status_code == 404
        assert stranger.get("/documents").json() == []
        assert stranger.get("/documents", params={"query": "quasar"}).json() == []
        assert stranger.get("/users").status_code == 403
        assert stranger.delete(f"/users/{user_ids[0]}/sessions").status_code == 403
        assert httpx.get("http://api:8000/api/v1/documents").status_code == 401
        spoofed = owner.post("/documents", files={
            "file": ("fake.pdf", b"not pdf", "application/pdf")
        })
        assert spoofed.status_code == 415
        with zipfile.ZipFile(source, "a") as archive:
            # Standard harmless antivirus test signature, not executable malware.
            archive.writestr("eicar.com", b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-"
                             b"ANTIVIRUS-TEST-FILE!$H+H*")
        infected = owner.post("/documents", files={"file": ("test.docx", source.getvalue(), mime)})
        assert infected.status_code == 202
        infected_id = infected.json()["id"]
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            record = owner.get(f"/documents/{infected_id}").json()
            if record["status"] in {"ready", "rejected", "failed"}:
                break
            time.sleep(1)
        assert record["status"] == "rejected", record
        assert record["entities"] == []
        assert record["extracted_metadata"] is None
        with SessionLocal() as session:
            from uuid import UUID
            stored = session.get(Document, UUID(infected_id))
            assert stored.storage_key is None
            assert stored.extracted_text is None
        assert owner.post(f"/documents/{infected_id}/retry").status_code == 409
        old_access = owner.headers["Authorization"]
        refreshed = owner.post("/auth/refresh")
        assert refreshed.status_code == 200
        assert owner.get("/users/me").status_code == 401
        owner.headers["Authorization"] = f"Bearer {refreshed.json()['access_token']}"
        assert owner.get("/users/me").status_code == 200
        assert old_access != owner.headers["Authorization"]
        assert owner.post("/auth/logout").status_code == 204
        assert owner.get("/users/me").status_code == 401
        assert owner.post("/auth/refresh").status_code == 401
        with httpx.Client(base_url="http://api:8000/api/v1", timeout=30) as other_session:
            login = other_session.post("/auth/token", json={"email": email, "password": password})
            assert login.status_code == 200
            other_session.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
            assert stranger.post("/auth/logout-all").status_code == 204
            assert stranger.get("/users/me").status_code == 401
            assert other_session.get("/users/me").status_code == 401
            assert other_session.post("/auth/refresh").status_code == 401
    finally:
        for client in clients:
            client.close()
        with SessionLocal() as session:
            storage = ObjectStorage(get_settings())
            records = session.scalars(select(Document).where(Document.owner_id.in_(user_ids)))
            for document in records:
                for key in (document.storage_key, document.quarantine_key):
                    if key:
                        storage.delete(key)
                session.delete(document)
            session.flush()
            for user_id in user_ids:
                user = session.get(User, user_id)
                if user:
                    session.delete(user)
            session.commit()
