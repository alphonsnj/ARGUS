# Production readiness gates

The local development stack is not approved for production deployment.

## Required deployment decisions

- Choose hosting provider, region and hostname; provision TLS and secret storage.
- Choose MFA policy and identity-provider integration, if any.
- Set retention, recovery-point/recovery-time targets and storage quotas.

## Implemented guardrails

Set APP_ENV=production, COOKIE_SECURE=true, explicit HTTPS CORS_ORIGINS and
ALLOWED_HOSTS for the real API hostname. The application validates these settings.
AUTH_RATE_LIMIT_PER_MINUTE defaults to 20 for login and refresh per client IP.
Configure trusted proxy hops deliberately; a shared proxy address can otherwise
rate-limit all users together. Never trust arbitrary forwarded headers.

Python runtime dependencies are hash-locked in apps/api/requirements.lock and
audited in CI. Regenerate the lock with uv pip compile pyproject.toml
--python-version 3.12 --generate-hashes -o requirements.lock, then rebuild/test.

## Open engineering work

- TLS ingress, production Compose/deployment configuration and external secret store.
- MFA enforcement and immediate access-token/session revocation (logout currently
  revokes refresh tokens; issued access tokens remain valid until expiry).
- Durable business audit events, external log retention and alerts.
- Automated database/object-store backups and a measured isolated restore drill.
- Crash-window orphan-object cleanup and idempotent upload/deduplication policy.
- Quotas and representative load tests; cursor pagination for very large datasets.
- Safe Redis stream retention that preserves pending work.
- Broader browser/OCR compatibility and independent security review.

## Container vulnerability gate

A local Trivy HIGH/CRITICAL scan on 2026-09-17 still reported 84 Debian package
findings with no fixed version supplied by the scanner, plus two pip-bundled
Python component findings (msgpack and setuptools). These are scanner entries,
not 86 unique exploitable vulnerabilities. Upgrading installed setuptools alone
does not resolve a vendored copy. Findings require triage/remediation; none are
silently waived. A clean application requirements audit is not a clean image audit.
Web and infrastructure images also need a complete production vulnerability review.

Keep the main PostgreSQL and MinIO volumes intact during all testing. Use a
separate Compose project and synthetic data for destructive recovery drills.

## Bounded document lists

GET /api/v1/documents now defaults to limit=50, accepts limit=1..100 and
offset=0..10000, and retains the existing array response. Results sort by
created_at descending then ID descending and remain owner/search scoped.
The UI shows 20 records per page, with a one-record lookahead for Next.
Search changes and successful uploads return to the first page.
Offset pages are not a snapshot: concurrent insertions can shift page boundaries.
Use a cursor/snapshot design before workloads require deep or immutable paging.

Verification: API pagination query/validation tests and scripts/qa-pagination.mjs
(UI-only mocked API contract test on a local Next server at port 3100).
