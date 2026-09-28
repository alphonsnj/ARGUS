# PostgreSQL patch upgrade: 2026-09-28

The local stack now uses PostgreSQL 16.15, pinned to the tested manifest:
`postgres:16.15-alpine@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea`.
The existing PostgreSQL volume was retained. Redis and MinIO were not upgraded.

## Evidence

- An isolated 16.4 fixture was backed up, stopped, and restarted with 16.15 using
  the same synthetic volume; schema/data/search/audit checks passed.
- The 16.4 archive was restored into a separate empty 16.15 database. Object
  bytes/metadata, foreign keys, entities, search, audit mutation guards and the
  restricted runtime login checks passed.
- Before the local cutover, the main database and object store were backed up
  to ignored `backups/pre-postgres-1615-20260928`. Keep this private.
- Local preflight found only plpgsql, no partitioned tables or replication slots,
  and only B-tree/GIN index methods. After the upgrade, no database or indexed
  collation-version mismatches were found.
- Alembic remains at 20260919_0003. The API still connects as argus_runtime.
- All 36 API tests, Ruff, strict mypy and the browser workflow passed after the
  local upgrade. The standard 16.15-to-16.15 recovery drill also passed.

The synthetic test is reproducible and included in CI:

```sh
node scripts/qa-backup.mjs --postgres-upgrade
```

Without that flag, the recovery drill uses the pinned current image at both ends.
Only the newly created synthetic projects/volumes are removed by the drill; its
archive is retained. Main volumes must never be deleted to perform an upgrade.

## Security result

The same refreshed Trivy database reported 85 HIGH/CRITICAL entries on the old
16.4 image and 22 on the tested 16.15 image. All 22 remaining entries are Go
standard-library findings in `/usr/local/bin/gosu`; the Alpine package result was
zero at these severities. No findings were suppressed or accepted as harmless.
Deployment remains blocked pending component remediation/reachability review.
Counts describe this local architecture and scan date, not a timeless guarantee.
Reports: ignored `backups/security-2026-09-28T17-41-48.303Z`.

## Operational boundaries

This was a local development upgrade, not a production deployment. For any other
installation, take a fresh backup, validate restore and review installed extensions,
replication, partitions and collations before stopping writers and upgrading.
Keep original volumes/images and private runtime credentials for recovery; if a
rollback is needed, stop writers and validate a restore into a separate project
before cutover. Do not overwrite the only copy of evidence or automatically reuse
an upgraded data directory with an older image.

PostgreSQL documents same-major patch compatibility, but also release-specific
checks in the [16.15 notes](https://www.postgresql.org/docs/16/release-16-15.html),
[16.10 notes](https://www.postgresql.org/docs/16/release-16-10.html) and
[16.5 notes](https://www.postgresql.org/docs/16/release-16-5.html).
