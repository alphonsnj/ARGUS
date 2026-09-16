from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import RefreshToken, Role, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email.lower()))

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def create_refresh_token(
        self, user: User, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        token = RefreshToken(user_id=user.id, token_hash=token_hash, expires_at=expires_at)
        self._session.add(token)
        self._session.commit()
        return token

    def get_active_refresh_token(self, token_hash: str, now: datetime) -> RefreshToken | None:
        return self._session.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > now,
            )
        )

    def revoke_refresh_token(self, token: RefreshToken, now: datetime) -> None:
        token.revoked_at = now
        self._session.commit()

    def role(self, name: str) -> Role | None:
        return self._session.scalar(select(Role).where(Role.name == name))

    def list_users(self) -> list[User]:
        return list(self._session.scalars(select(User).order_by(User.created_at.desc())))
