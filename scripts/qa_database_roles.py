"""Run only in the synthetic recovery drill. Proves actual runtime-login permissions."""

import os
import secrets
from uuid import uuid4

import psycopg

from provision_runtime import connect, provision, rotate

url = provision(os.environ["DATABASE_URL"], secrets.token_hex(32))
with connect(url) as connection:
    assert connection.execute("SELECT current_user").fetchone()[0] == "argus_runtime"
    connection.execute("SELECT id FROM users FOR UPDATE")
    connection.execute("SELECT id FROM documents")
    connection.execute("INSERT INTO audit_events (id, action) VALUES (%s, %s)",
                       (uuid4(), "audit.listed"))
    # Prove privilege denial, not merely the append-only trigger.
    for statement in (
        "UPDATE audit_events SET action = 'changed'",
        "DELETE FROM audit_events", "TRUNCATE audit_events",
        "ALTER TABLE audit_events DISABLE TRIGGER ALL",
        "DROP TABLE audit_events", "UPDATE alembic_version SET version_num = 'bad'",
        "CREATE TABLE public.unwanted (id int)", "CREATE TEMP TABLE unwanted (id int)",
        "CREATE SCHEMA unwanted", "CREATE ROLE unwanted",
        "DELETE FROM users", "UPDATE users SET is_active = false",
    ):
        try:
            with connection.transaction():
                connection.execute(statement)
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError(f"Unexpected runtime permission: {statement}")
    connection.rollback()
try:
    provision(os.environ["DATABASE_URL"], secrets.token_hex(32))
except RuntimeError:
    pass
else:
    raise AssertionError("Provisioning must refuse an existing role")
rotated = rotate(os.environ["DATABASE_URL"], secrets.token_hex(32))
with connect(rotated) as connection:
    assert connection.execute("SELECT current_user").fetchone()[0] == "argus_runtime"
try:
    with connect(url):
        raise AssertionError("Old runtime password still accepted")
except psycopg.OperationalError:
    pass
print("PASS runtime login, row locks, audit insert and denied DDL/audit mutation/admin writes")
