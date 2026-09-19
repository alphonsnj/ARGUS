# ARGUS

AI-powered investigation intelligence platform. ARGUS assists authorized investigators; it does not make final investigative decisions or definitive identifications.

## Current foundation

- Next.js 15 / React 19 web workspace and shared, accessible UI primitives
- FastAPI / SQLAlchemy 2.0 API with Alembic migrations
- PostgreSQL, Redis, MinIO, and ClamAV local topology
- Argon2id password verification, JWT access-token issuance, persisted roles, and refresh-token data model
- Dockerfiles and GitHub Actions quality gates
- Authenticated workspace shell, operational overview, and role-protected user directory
- Private document intake with quarantine storage, malware scanning, OCR/text extraction, metadata extraction, and PostgreSQL full-text indexing

### Local setup

1. Copy `.env.example` to `.env` and replace every example secret with a unique local value.
2. Run `docker compose up --build`.
3. Apply database migrations: `docker compose run --rm migrate`.
4. Provision the first administrator: `docker compose run --rm --entrypoint python migrate -m app.cli.bootstrap_admin --email admin@example.com`. You will be prompted for a password; this command never accepts it as an argument.
5. Enable the [restricted runtime database login](docs/database-roles.md) before further hardening or deployment.

The API health endpoint is `http://localhost:8000/api/v1/health`; OpenAPI documentation is at `http://localhost:8000/docs`.

The document worker consumes a Redis Stream and reconciles committed queued/processing rows from PostgreSQL, so unavailable Redis notifications do not strand accepted uploads. A submitted file remains in quarantine until ClamAV accepts it; failures remain private and can be retried from the Documents page. Search runs against extracted text and status refreshes automatically.

Set `COOKIE_SECURE=true` in every HTTPS deployment. It remains `false` only for local HTTP development.

For local web-only development, install dependencies with `npm install` and run `npm run dev`. API development requires Python 3.12 or later.

See [architecture documentation](docs/architecture.md) for package ownership and foundation boundaries.

See [ingestion verification](docs/ingestion-verification.md) for repeatable security,
OCR, outage, and browser checks and the remaining release limitations.
