import argparse
import getpass

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Role, User

ROLES = {
    "Super Administrator": "Full platform administration",
    "State Administrator": "State-level administration",
    "Department Administrator": "Department-level administration",
    "Investigator": "Investigation workspace access",
    "Analyst": "Analysis workspace access",
    "Read-Only Auditor": "Read-only audit access",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision the first ARGUS Super Administrator.")
    parser.add_argument("--email", required=True, type=str.lower)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    password = getpass.getpass("Administrator password: ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")

    with SessionLocal() as session:
        if session.scalar(select(User).where(User.email == args.email)) is not None:
            raise SystemExit("A user with that email already exists.")
        roles: dict[str, Role] = {}
        for name, description in ROLES.items():
            role = session.scalar(select(Role).where(Role.name == name))
            if role is None:
                role = Role(name=name, description=description)
                session.add(role)
            roles[name] = role
        session.flush()
        session.add(
            User(
                email=args.email,
                password_hash=hash_password(password),
                roles=[roles["Super Administrator"]],
            )
        )
        session.commit()
    print(f"Provisioned Super Administrator: {args.email}")


if __name__ == "__main__":
    main()
