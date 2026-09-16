# Ingestion verification

The opt-in `apps/api/tests/test_ingestion_live.py` test exercises the running
API, Redis worker queue, ClamAV, MinIO, PostgreSQL, DOCX extraction, PNG OCR,
scanned-PDF OCR, and full-text search. It creates disposable users and documents and removes those records
and objects afterward. It does not use or reset an existing administrator.

Start the stack with `docker compose up -d --build` and apply migrations with
`docker compose exec api alembic upgrade head` before running it.

From the repository root:

```sh
docker run --rm --user 0 --network argus_default --env-file .env \
  -e ARGUS_LIVE_TEST=1 \
  -v "$PWD/apps/api/pyproject.toml:/app/pyproject.toml:ro" \
  -v "$PWD/apps/api/tests:/app/tests:ro" \
  --entrypoint sh argus-api \
  -c 'pip install "pytest>=8.3,<9" "pytest-cov>=6,<7" && python -m pytest tests -q'
```

Without `ARGUS_LIVE_TEST=1`, the integration test is skipped. Unit regressions
cover enum serialization, scanner stream framing and fragmented responses,
fail-closed scanner behavior, email punctuation extraction, and mixed-PDF
page routing (OCR only for pages without extractable text).

`test_recovery_live.py` seeds a processing record and an abandoned pending
message in an isolated Redis stream. A worker subprocess must reclaim it,
finish processing, and acknowledge the message. It also verifies that an active
PostgreSQL advisory lock prevents concurrent processing of that document.
This simulates the state left by a crashed worker; it is not a full host-crash test.

Each worker has a unique consumer ID and checks for messages idle for at least
60 seconds using [Redis XAUTOCLAIM](https://redis.io/docs/latest/commands/xautoclaim/).
A connection-scoped PostgreSQL advisory lock protects processing across commits;
the database releases it when the connection dies. Terminal ready/rejected
records are not processed again. Failed records still use the explicit retry API.
OCR has a 60-second per-image timeout and PDFs have a 100-page limit.

## Security checks

`test_ingestion_security_live.py` creates two ordinary accounts. It checks that
another account cannot list, search, read, or retry the owner's document, that
unauthenticated access is rejected, and that ordinary accounts cannot list users.
It submits a DOCX containing the harmless EICAR antivirus signature and verifies
rejection without extracted text, entities, or a promoted storage key. Spoofed
PDF content is refused. Logout returns 204 and the refresh session is revoked.

## Isolated outage checks

These commands create a separate `argus-validation` project with its own data
volumes. Never run outage commands against a production Compose project.

```sh
docker compose -p argus-validation -f docker-compose.yml -f docker-compose.validation.yml up -d --build postgres redis minio clamav api document-worker
docker compose -p argus-validation -f docker-compose.yml -f docker-compose.validation.yml exec -T api alembic upgrade head
node scripts/qa-outages.mjs
```

The script stops Redis and verifies that an accepted upload completes through
database reconciliation. It pauses ClamAV briefly to hold a job in processing,
kills the worker with SIGKILL, and verifies recovery. It stops PostgreSQL after
accepting an upload, expects API 503 during the outage, and verifies completion
after restart. Document checksums must remain unchanged. Dependencies are
restored in a finally block. This covers container/process outages, not disk
loss, host power loss, or all network-partition timing windows.

Workers reconcile up to 20 queued/processing database records each loop under
the same advisory locks used for stream delivery. Redis notification failure
therefore does not invalidate an already committed upload. Processing errors
remain failed for explicit retry rather than being automatically retried forever.

## Browser checks

With the normal Compose stack running, Google Chrome installed, and `npm ci`
completed:

```sh
node scripts/qa-browser.mjs
```

This uses a disposable account and real services: sign in, retry a failed
fixture, upload a DOCX, wait for automatic status updates, search/clear search,
check a 390px viewport for overflow, sign out, and verify protected-route redirect.
It also fails on JavaScript page errors. Screenshots are saved under
`/tmp/argus-qa-desktop.png` and `/tmp/argus-qa-mobile.png`. QA accounts and objects
are removed afterward; no existing administrator password is used or reset.

## Release limitations

Passing these checks is a local development checkpoint, not a production
security certification. Before deployment:

- Add TLS, secure-cookie enforcement, rate limits, audit events, and an explicit
  MFA/session-revocation policy. Existing stateless access tokens remain valid
  until expiry (15 minutes by default) after logout; refresh tokens are revoked.
- Lock/audit Python dependencies and scan container images. The npm audit is
  separate and does not certify those runtimes.
- Validate backup restoration, volume loss, extended network partitions, and
  concurrent high-volume uploads. Health currently includes liveness, not a
  comprehensive readiness/SLO monitor.
- Add storage lifecycle reconciliation for orphaned quarantine/promoted objects
  at crash/commit boundaries, upload idempotency for ambiguous client retries,
  queue retention/dead-letter policy, pagination, and resource quotas.
- Extend corpus coverage for complex PDFs, multilingual OCR, encrypted files,
  adversarial archives, and additional browsers. OCR quality is not guaranteed.
