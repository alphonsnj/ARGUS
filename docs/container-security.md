# Container security checkpoint: 2026-09-20

Update 2026-09-28: the PostgreSQL row below is historical. A tested local upgrade
to 16.15 reduced its count from 85 to 22; see [upgrade evidence](postgres-upgrade.md).

The production vulnerability gate remains **blocked**. Passing unit tests or
dependency audits does not imply clean container images.

## Scan results

Trivy 0.69.3, refreshed vulnerability database, HIGH/CRITICAL, no ignored statuses
or vulnerabilities. Counts are package/advisory entries, not unique exploitable
CVEs. These local images are architecture-specific; deployment images must be
rescanned on the target architecture. Zero findings is not proof of security.

| Local image | Before | After this change | Entries with scanner-listed fixes remaining |
| --- | ---: | ---: | ---: |
| API and worker runtime | 86 | 84 | 0 |
| Web runtime | 13 | 0 | 0 |
| PostgreSQL 16.4-alpine (unchanged) | 85 | 85 | 85 |
| Redis 7.4-alpine (unchanged local image) | 2 | 2 | 2 |
| MinIO RELEASE.2024-10-13T13-34-11Z (unchanged) | 116 | 116 | 116 |
| ClamAV 1.4_base (unchanged local image) | 0 | 0 | 0 |

API after-scan image ID: `sha256:40e9e71eff04274004d935f0b12b6989565266936ead84d941f0baa2daa987cb`.
Web after-scan image ID: `sha256:235fea5485457d6277a03aab01154cc6a25736f5d4589a32a2684b8f6e0ccf31`.
Mutable tags may later resolve to different images. Raw reports are kept locally
under ignored `backups/security-*`; scan output records the exact image IDs.

## Changes

- Removed pip/setuptools from the final API/worker image after installation.
  This removed findings for bundled msgpack and setuptools; it does not patch OS
  packages. A separate `development` build target retains installation tools for tests.
- Rebuilt the web image from the refreshed Node base, applied Alpine updates,
  and removed npm/corepack/yarn from the runtime (not the build stage).
- Excluded local backups from the web Docker build context and env/cache files
  from the API build context. Existing historical builder cache was not deleted.
- Added runtime import/tool-absence checks to CI.

The updated runtime images are active locally. Previous local image tags ending
in `pre-security-20260920` are retained for rollback. No database or object-store
image/volume was upgraded or removed in this checkpoint.

Validation: 36 API tests, Ruff, strict mypy, browser login/upload/processing/search/
retry/logout, and the isolated backup/restore plus runtime-role drill passed.
The active API still uses argus_runtime. Packaging tools were removed only from
generated runtime images; source files and existing local rollback images remain.

## Repeat the scan

```sh
node scripts/scan-images.mjs
# Or select already-built local images:
node scripts/scan-images.mjs argus-api argus-web
```

Requires Docker, the named local images and access to the vulnerability database.
The scanner container mounts the Docker socket: use only a trusted local engine
and scanner image. The script returns nonzero for any finding or incomplete scan,
writes JSON evidence under backups, and never uses --ignore-unfixed. It does not
pull/upgrade production images or alter running services. Normal CI is not a
vulnerability waiver; run this separate gate before release.

## Next remediation work

1. Test a supported PostgreSQL 16 patch image against an isolated restored backup,
   including runtime grants and migrations, then schedule the backed-up upgrade.
2. Refresh and scan a compatible Redis image, and test queue recovery/persistence.
3. Evaluate a supported MinIO upgrade or replacement and validate object metadata,
   quarantine/evidence access and backup/restore before any real-data cutover.
4. Triage the 84 Debian entries against vendor advisories and reachability, or
   evaluate a supported base with fewer findings. No listed fix is not a waiver.

Trivy's [vulnerability guidance](https://trivy.dev/docs/v0.69/guide/scanner/vulnerability/)
explains vendor severity and unfixed findings. Pip's
[vendoring policy](https://pip.pypa.io/en/stable/development/vendoring-policy/)
explains why upgrading a top-level package does not necessarily change its bundled copy.
