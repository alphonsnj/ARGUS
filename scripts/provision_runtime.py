"""Provision a new non-owner login; run with owner credentials, never in the API."""

import json
import os
import secrets
import sys

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

from app.core.config import Settings

ROLE = "argus_runtime"


def connect(url: str, **overrides):
    parsed = make_url(url)
    parameters = dict(parsed.query)
    parameters.update(host=parsed.host, port=parsed.port or 5432, dbname=parsed.database,
                      user=parsed.username, password=parsed.password)
    parameters.update(overrides)
    return psycopg.connect(**parameters)


def provision(url: str, password: str) -> str:
    with connect(url) as connection:
        if connection.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (ROLE,)).fetchone():
            raise RuntimeError("Runtime role already exists; refusing implicit credential rotation")
        # A fresh role avoids inherited memberships, ownership and stale grants.
        connection.execute(sql.SQL(
            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
        ).format(sql.Identifier(ROLE), sql.Literal(password)))
        database = connection.execute("SELECT current_database()").fetchone()[0]
        connection.execute(sql.SQL("REVOKE CREATE, TEMPORARY ON DATABASE {} FROM PUBLIC")
                           .format(sql.Identifier(database)))
        connection.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        connection.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}")
                           .format(sql.Identifier(database), sql.Identifier(ROLE)))
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}")
                           .format(sql.Identifier(ROLE)))
        grants = {
            "users": "SELECT, UPDATE (last_login_at)",
            "roles": "SELECT",
            "user_roles": "SELECT",
            "refresh_tokens": "SELECT, INSERT, UPDATE",
            "documents": "SELECT, INSERT, UPDATE",
            "document_entities": "SELECT, INSERT, UPDATE, DELETE",
            "audit_events": "SELECT, INSERT",
        }
        for table, privileges in grants.items():
            connection.execute(sql.SQL("GRANT {} ON TABLE public.{} TO {}")
                               .format(sql.SQL(privileges), sql.Identifier(table),
                                       sql.Identifier(ROLE)))
    return make_url(url).set(username=ROLE, password=password).render_as_string(hide_password=False)


def rotate(url: str, password: str) -> str:
    with connect(url) as connection:
        role = connection.execute(
            "SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
            "FROM pg_roles WHERE rolname = %s", (ROLE,)
        ).fetchone()
        if role != (False, False, False, False, False):
            raise RuntimeError("Not the expected restricted runtime role")
        connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}")
                           .format(sql.Identifier(ROLE), sql.Literal(password)))
    return make_url(url).set(username=ROLE, password=password).render_as_string(hide_password=False)


if __name__ == "__main__":
    # Output is a secret-bearing JSON document for a private env-file creation step.
    # Never print this directly to a terminal or CI log.
    try:
        allowed = {name.upper() for name in Settings.model_fields}
        runtime = {key: value for key, value in os.environ.items() if key in allowed}
        if any(any(char in value for char in "\r\n\0") for value in runtime.values()):
            raise RuntimeError("Unsupported multiline runtime setting")
        if sys.argv[1:] not in ([], ["--rotate"]):
            raise RuntimeError("Unknown option")
        operation = rotate if sys.argv[1:] else provision
        runtime_url = operation(os.environ["DATABASE_URL"], secrets.token_hex(32))
        runtime["DATABASE_URL"] = runtime_url
        print(json.dumps(runtime))
    except Exception:
        print("Runtime provisioning failed; transaction rolled back. Check role/schema prerequisites.",
              file=sys.stderr)
        sys.exit(1)
