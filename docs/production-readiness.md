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
- MFA enforcement, enrollment and recovery policy.
- Durable business audit events, external log retention and alerts.
- Off-site encrypted backup storage, production scheduling/alerts and retention.
  Local backup/restore tooling and a synthetic isolated drill are implemented;
  see [backup and restore](backup-and-restore.md).
- Crash-window orphan-object cleanup and idempotent upload/deduplication policy.
- Representative load tests; cursor pagination for very large datasets.
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

## Quotas and session revocation

Uploads now enforce MAX_USER_STORAGE_BYTES (default 1 GiB) and MAX_USER_DOCUMENTS
(default 1,000). All document rows count, including failed/rejected records;
these are logical intake limits, not a measurement of physical bucket usage.
An owner-row lock serializes quota checks until the document is committed.
Over-limit requests return 413 before creating an object. Existing documents
are never deleted automatically. Production limits still need operator review.

Access tokens carry a required session ID, checked against active database
refresh-session records on every authenticated request. Logout/rotation invalidate
the associated old access token for subsequent requests. Already-running requests
are not cancelled. Inactive accounts are denied on every request.
POST /api/v1/auth/logout-all revokes the caller's sessions. Super Administrators
can DELETE /api/v1/users/{user_id}/sessions to revoke another user's sessions.
These endpoints are available in the API; UI management controls remain future work.
Session revocation does not prevent a new valid login; disable an account when
access must remain blocked. Old access tokens without session IDs are rejected;
existing valid refresh cookies can renew them. Otherwise sign in again.

Refresh rotation and all-session revocation serialize per user; rotation revokes
the old token and creates its replacement in the same transaction. The browser
shares in-flight refresh operations within a tab. Cross-tab requests can still
race over the shared cookie and may require retry/sign-in.

Validation on 2026-09-17: 34 API tests passed with live integration enabled,
including old-access rejection after rotation/logout, logout-all across sessions,
ordinary-user rejection of admin revocation, and concurrent quota enforcement.
Frontend build/lint/type checking and browser workflow passed. The client test
scripts/qa-auth-client.mjs confirms 20 concurrent 401s share one refresh operation.
