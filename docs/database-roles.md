# Runtime database permissions

The API and document worker can use a dedicated `argus_runtime` login instead of
the database owner. It cannot create roles, schemas or tables, alter/drop tables,
change the migration version, disable audit triggers, or modify/delete audit rows.
It has no role memberships, superuser, replication or RLS-bypass privileges.

Grants are explicit: read users/roles/memberships, lock users via update permission
on last_login_at only, create/update sessions and documents, replace extracted
entities, and insert/read audit events. These are service-wide permissions, not
per-user database isolation; API ownership/authorization checks still matter.
No automatic default grants are used: new migrations must review required grants.

## Existing local installation

From the repository root, with PostgreSQL running and current migrations applied:

```sh
node scripts/setup-runtime.mjs
```

This provisions a fresh login and writes a generated 0600 `.env.runtime` containing
only application settings. Owner credentials and MinIO root environment variables
are excluded. The script refuses an existing output file or role; it does not
silently reset a password. It revokes PUBLIC schema CREATE and database
CREATE/TEMPORARY privileges. Use only on ARGUS's dedicated database, not a shared
database with unrelated applications relying on those PUBLIC permissions.

Set `ARGUS_APP_ENV_FILE=.env.runtime` in `.env`, then:

```sh
docker compose up -d --no-deps --force-recreate api document-worker
```

Verify login, upload/processing and audit reads. Keep both env files private and
out of Git. Future application setting changes must also update `.env.runtime`;
the generated file is a snapshot, not a live reference to `.env`.

Migrations now use the separate operations container with owner credentials:

```sh
docker compose run --rm migrate
```

Do not run Alembic inside the restricted API container. Administrative bootstrap
uses the operations container with a Python entrypoint. Backup tooling continues
to use the PostgreSQL owner. Restores intentionally omit grants/owners and must
re-provision runtime credentials before cutover; never reuse production secrets
in a synthetic drill. The isolated CI drill verifies real runtime login and
denials after restoring.

If setup fails, an empty private file may remain. Do not blindly rerun or delete
an existing role: check whether provisioning committed and recover/rotate the
credential deliberately. A failed generated-file write after DB commit requires
operator recovery. After safely moving the failed/old env file aside, explicit
`node scripts/setup-runtime.mjs --rotate` rotates only the restricted login's
password and writes a new private file. Coordinate downtime/recreation: old
credentials stop working for new connections. No existing tables or evidence
are dropped by setup.

## Remaining production gates

The Compose fallback remains `.env` for compatibility; separation is enabled only
when `ARGUS_APP_ENV_FILE` selects the private runtime file. This is not a separate
restricted migration login: the operations container still uses the existing
owner, so access to it must be tightly controlled. Production should use secret
injection and dedicated deployment credentials, not local env files. Database
owners can still bypass triggers; independently retained audit storage is needed.

Permission design follows the [PostgreSQL privilege model](https://www.postgresql.org/docs/16/ddl-priv.html).

## Validation checkpoint (2026-09-19)

The local API and worker were switched to the restricted login after backup.
All 36 API tests and the browser workflow passed with the services running under
that login (test fixture setup/cleanup still uses the owner). Runtime container
inspection confirmed the owner environment variables were absent. The migration
container independently reported the current Alembic head. The isolated recovery
drill verified denied DDL/audit mutation, row locking, duplicate-setup refusal and
explicit password rotation; no main database volumes were removed.
