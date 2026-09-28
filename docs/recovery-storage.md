# Recovery storage compatibility fixture

The old MinIO registry image is no longer reliably retrievable on fresh CI
machines. The isolated recovery Compose file instead builds official source at
commit `d10bb7e1b667c2df72c394ef1fa52ab4a6802d0f`, the dereferenced
`RELEASE.2024-10-13T13-34-11Z` tag. The build checks the fetched commit and Go
module checksums. Go and Alpine base images are pinned by manifest digest.

Build from the repository root:

```sh
docker compose -f docker-compose.recovery.yml build minio
node scripts/qa-backup.mjs
node scripts/qa-backup.mjs --postgres-upgrade
```

This image is a compatibility test fixture, not an approved production service.
It preserves the old storage implementation to exercise backup/restore without
trusting an unofficial binary mirror. Rebuilding with a newer compiler does not
fix all vulnerabilities in the archived application or its dependencies. MinIO
upstream is archived; a supported production storage choice and migration plan
remain required. The main Compose image, credentials and evidence volumes are
unchanged. Recovery services publish no host ports.

Source: [official MinIO commit](https://github.com/minio/minio/tree/d10bb7e1b667c2df72c394ef1fa52ab4a6802d0f).
MinIO is AGPLv3-licensed; the runtime includes its LICENSE. Anyone distributing
this built image must satisfy the license's corresponding-source obligations;
this repository publishes the build recipe, not a replacement binary service.

The fixture runs as a non-root user and uses an HTTP readiness probe, so it does
not need the separate MinIO client binary. Image pulls are disabled for the local
fixture tag; explicitly rebuild it after changing the recipe. CI builds it before
running either recovery drill.

Local verification on 2026-09-28: both normal backup/restore and PostgreSQL
16.4-to-16.15 restart/restore drills passed with this fixture. Checks include
binary object contents and metadata, relationships/search, append-only audit,
restricted runtime credentials and corrupted/nonempty restore refusal. Main
storage was not migrated. These synthetic checks do not establish production
capacity or eliminate application vulnerabilities.
