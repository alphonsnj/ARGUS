# Durable audit events

Migration 20260919_0003 adds PostgreSQL audit_events. No existing evidence or
authentication tables are rewritten. Apply migrations before starting updated
API/worker images. The API exposes GET /api/v1/audit to Super Administrators only,
with limit 1..100 (default 50) and offset 0..10000.

Events store only event name, actor ID, subject ID, timestamp and server-generated
request ID. They exclude filenames, evidence contents, passwords, tokens, email
addresses, search terms and IP addresses. Actor/subject IDs intentionally have no
foreign keys: account or evidence cleanup must not remove audit history.
Background worker events have no human actor or HTTP request ID.

## Coverage and guarantees

- Document creation, processing, ready/failed/rejected transitions and retries.
- Authorized document listing, searches and detail reads (not the search query).
- Session creation/revocation, all-session revocation, failed password login.
- Administrator audit-history reads.

State-change events are inserted in the same PostgreSQL transaction as the
mutation. Rollback removes both. Read events must commit before the endpoint
returns a successful response. No best-effort fallback silently skips these
events. Audit storage failure can make the relevant operation unavailable.
Request IDs link HTTP events to structured server logs.

A PostgreSQL trigger rejects UPDATE, DELETE and TRUNCATE on audit_events. This
is an append-only application guard, **not cryptographic tamper evidence**:
database owners/superusers can disable triggers, drop tables or restore backups.
Production needs separate restricted runtime/migration roles and an independently
retained log sink. There is no automatic audit deletion or retention schedule.

Not yet covered: every authorization denial, refresh rejection, CLI bootstrap,
direct database changes, or proof of file viewing/download. Existing stdout
request logs remain separate. There is no audit browsing UI, export job or alert
pipeline yet. Rate limits and capacity/retention planning remain important because
polling and failed login attempts can generate many events.

Backups include this table and its trigger. Restores must remain isolated until
verified. Synthetic integration tests intentionally retain a small number of
anonymous audit events; attempting to delete them would defeat the guard.

## Validation checkpoint (2026-09-19)

- Ruff and strict mypy passed; all 36 API tests passed against the local stack.
- Live checks verified transaction rollback, rejected update/delete/truncate,
  administrator access and rejection of non-administrator audit reads.
- Browser login, upload, processing, search, retry, mobile layout and logout passed.
- An isolated backup/restore preserved audit records and all three mutation guards.

These checks validate the implemented scope, not production security certification.
