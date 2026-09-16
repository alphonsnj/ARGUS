# ARGUS architecture foundation

ARGUS is organized as a workspace so application boundaries stay explicit as the platform grows.

- `apps/web`: Next.js 15 application. It owns composition, routing, and browser-only concerns.
- `apps/api`: FastAPI application. Its request path is API router → dependency-injected service → repository → SQLAlchemy 2.0 session.
- `packages/ui`: tokenized, accessible React primitives shared by web surfaces.
- `packages/auth`, `packages/database`, `packages/ai`, `packages/search`, and `packages/shared`: reserved package boundaries. They are introduced only when their first real cross-application capability exists.

The API is intentionally PostgreSQL-first: UUID identifiers, foreign keys, a consistent naming convention, and Alembic migrations. Redis and S3-compatible object storage are available through the local service topology but are not yet wired to product workflows.

The authentication foundation uses Argon2id password hashes, short-lived signed access tokens, role persistence, and a refresh-token table. The web app holds access tokens only in session storage and renews them from a HttpOnly, SameSite refresh cookie. `/users/me` requires a valid bearer token; the user directory requires the `Super Administrator` role.

The Sprint 2 dashboard is intentionally operational rather than synthetic: it shows verified identity and foundation readiness, but does not invent case, evidence, or search metrics. User provisioning remains a deliberate CLI operation until the full user-administration workflow is separately approved. MFA enrollment and device verification remain future increments.

## Sprint 3 document ingestion

Documents are accepted only as PDF, DOCX, JPEG, PNG, or TIFF after extension and file-signature validation. The API streams the upload to a short-lived local file, stores it under a private MinIO quarantine prefix, persists the queued record, and appends the work item to a Redis Stream.

The dedicated `document-worker` consumes that stream. It retrieves the quarantined object, sends it to ClamAV using the `INSTREAM` protocol, extracts PDF/DOCX text or performs image OCR with Tesseract, derives high-confidence metadata and entities, and writes a PostgreSQL full-text `tsvector` index. Clean source objects are promoted to the permanent private prefix only after the scan passes. Scanner failures fail closed; malware is deleted and the document is marked rejected. Until case management exists, an investigator can only list or retrieve documents they uploaded.
