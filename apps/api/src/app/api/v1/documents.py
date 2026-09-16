import hashlib
import tempfile
import zipfile
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.core.config import Settings, get_settings
from app.models import Document, DocumentStatus
from app.repositories.documents import DocumentRepository
from app.services.queue import DocumentQueue
from app.services.storage import ObjectStorage

router = APIRouter(prefix="/documents", tags=["documents"])

SUPPORTED_TYPES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tiff",
}


class EntityResponse(BaseModel):
    kind: str
    value: str


class DocumentResponse(BaseModel):
    id: UUID
    original_filename: str
    content_type: str
    byte_size: int
    sha256: str
    status: DocumentStatus
    extracted_metadata: dict[str, object] | None
    failure_reason: str | None
    created_at: str
    updated_at: str
    entities: list[EntityResponse]


def response_model(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        original_filename=document.original_filename,
        content_type=document.content_type,
        byte_size=document.byte_size,
        sha256=document.sha256,
        status=document.status,
        extracted_metadata=document.extracted_metadata,
        failure_reason=document.failure_reason,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
        entities=[
            EntityResponse(kind=entity.kind, value=entity.value) for entity in document.entities
        ],
    )


def validate_file_signature(path: Path, content_type: str) -> None:
    with path.open("rb") as source:
        prefix = source.read(16)
    if content_type == "application/pdf" and prefix.startswith(b"%PDF-"):
        return
    if (
        content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        and zipfile.is_zipfile(path)
    ):
        with zipfile.ZipFile(path) as archive:
            uncompressed_size = sum(item.file_size for item in archive.infolist())
            is_safe_archive = (
                len(archive.infolist()) <= 2000
                and uncompressed_size <= 100 * 1024 * 1024
                and "word/document.xml" in archive.namelist()
            )
            if is_safe_archive:
                return
    if content_type == "image/jpeg" and prefix.startswith(b"\xff\xd8\xff"):
        return
    if content_type == "image/png" and prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    if content_type == "image/tiff" and prefix[:4] in {b"II*\x00", b"MM\x00*"}:
        return
    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Invalid file signature",
    )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_document(
    user: CurrentUser,
    session: DbSession,
    file: Annotated[UploadFile, File(description="PDF, DOCX, JPEG, PNG, or TIFF document")],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentResponse:
    content_type = (file.content_type or "").lower()
    filename = Path(file.filename or "document").name
    expected_extension = SUPPORTED_TYPES.get(content_type)
    suffix = Path(filename).suffix.lower()
    allowed_extensions = {expected_extension}
    if content_type == "image/jpeg":
        allowed_extensions.add(".jpeg")
    if content_type == "image/tiff":
        allowed_extensions.add(".tif")
    if expected_extension is None or suffix not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported document type",
        )
    digest = hashlib.sha256()
    size = 0
    with tempfile.TemporaryDirectory(prefix="argus-upload-") as directory:
        path = Path(directory) / "upload"
        with path.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Document exceeds upload limit",
                    )
                digest.update(chunk)
                destination.write(chunk)
        validate_file_signature(path, content_type)
        quarantine_key = f"quarantine/{uuid4()}/{filename}"
        ObjectStorage(settings).upload_file(path, quarantine_key, content_type)
    document = DocumentRepository(session).create(
        owner_id=user.id,
        original_filename=filename,
        content_type=content_type,
        byte_size=size,
        sha256=digest.hexdigest(),
        quarantine_key=quarantine_key,
    )
    DocumentQueue(settings).enqueue(document.id)
    return response_model(document)


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    user: CurrentUser,
    session: DbSession,
    query: Annotated[str | None, Query(min_length=2, max_length=200)] = None,
) -> list[DocumentResponse]:
    repository = DocumentRepository(session)
    return [response_model(document) for document in repository.list_for_owner(user.id, query)]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, user: CurrentUser, session: DbSession) -> DocumentResponse:
    document = DocumentRepository(session).get_for_owner(document_id, user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return response_model(document)


@router.post(
    "/{document_id}/retry",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_document(
    document_id: UUID,
    user: CurrentUser,
    session: DbSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentResponse:
    repository = DocumentRepository(session)
    document = repository.get_for_owner(document_id, user.id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.status is not DocumentStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only failed documents can be retried",
        )
    repository.requeue(document)
    DocumentQueue(settings).enqueue(document.id)
    return response_model(document)
