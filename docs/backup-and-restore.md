# Backup and isolated restore

These tools support the local Compose topology (PostgreSQL plus internal MinIO).
They do not configure an off-site backup service or a production schedule.

## Create a backup

Run from the repository root, with Docker running and the API image built:

```sh
mkdir -p backups
node scripts/backup.mjs backup argus backups/checkpoint-001
```

Use a new destination for every backup. Existing paths are refused. The tool
holds a per-project lock in `backups/.locks` to prevent overlapping operations
from this checkout. After a forced termination, inspect running processes before
manually removing a stale lock; do not run the tool concurrently from other checkouts.
The tool
stops whichever of `api` and `document-worker` are running, allows 120 seconds
for shutdown, dumps PostgreSQL and copies the current evidence bucket, then
restarts those services in a finally block. This causes API maintenance downtime;
do not run it during active intake without notifying users. Other writers and
direct object-store writes must also be stopped by the operator.

The archive includes a custom-format database dump, object bytes under hashed
filenames, original object keys, content types, user metadata, SHA-256 checksums,
and a completion manifest written last. Both quarantine and promoted evidence
are included. An archive without `manifest.json` is incomplete and cannot restore.
Redis is not archived: queued/processing documents are recovered from PostgreSQL
by the ingestion worker. S3 historical versions, bucket policies and credentials
are not archived. Retain deployment configuration/secrets separately and securely.

Archives contain confidential evidence and account/password-hash data. Directories
are mode 0700 and newly written files mode 0600. They are **not encrypted by this
tool**. Store them on an encrypted volume and use encrypted, access-controlled
off-site storage before relying on them for disaster recovery. Checksums detect
corruption, not deliberate tampering; restore only trusted archives.

## Restore without overwriting the running system

Start a new project with an unused name beginning `argus-restore-`:

```sh
docker compose -p argus-restore-review -f docker-compose.recovery.yml up -d --wait
node scripts/backup.mjs restore argus-restore-review backups/checkpoint-001 docker-compose.recovery.yml
```

The recovery Compose file publishes no ports. Restore rejects the main project,
running target API/workers, non-empty databases/buckets, incomplete manifests,
symlinks in archive paths, and checksum mismatches. Database import runs in one
transaction. Object import is not atomic with PostgreSQL: if an upload fails,
keep the failed target isolated and retry into a fresh empty project. Never use
`down --volumes` on the main project to make a restore possible.

Verify users, foreign keys, document statuses, search results and every referenced
object before any cutover. Production cutover, secret rotation, session invalidation
and DNS changes require a separate approved recovery plan.

## Repeatable drill

```sh
node scripts/qa-backup.mjs
```

The drill creates unique source/restore projects, applies real Alembic migrations,
seeds synthetic users/documents/entities and two objects, backs up, restores, and
checks database relationships, search vectors, exact binary bytes and object
metadata. It also checks refusal of corrupted objects, backup overwrite, restoring
to `argus`, and re-restoring over data. It reports backup/restore elapsed seconds.
Only its newly created synthetic project volumes are deleted afterwards; its
small synthetic archive is retained in the reported temporary directory.

Local drill on 2026-09-17 passed: backup 0.574 seconds, restore 1.568 seconds.
Database and object corruption, overlapping-operation locks, backup overwrite,
main-project restore and non-empty database restore were rejected. GitHub Actions
also runs the synthetic drill on pushes and pull requests.

Before production: choose retention, backup frequency, encryption key management,
off-site destination and recovery objectives. Automate with cross-host coordination,
failure alerts and periodic isolated drills. Tiny-fixture timings are not a
production RTO/RPO guarantee; load-test representative data volumes.
