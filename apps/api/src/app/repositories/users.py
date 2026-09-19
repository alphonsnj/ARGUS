from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken, Role, User
from app.repositories.audit import record_event


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
        self._session.flush()
        record_event(self._session, "session.created", token.id, actor_id=user.id)
        self._session.commit()
        return token

    def lock_user(self, user_id: UUID) -> None:
        self._session.execute(select(User.id).where(User.id == user_id).with_for_update())

    def get_active_refresh_token(
        self, token_hash: str, now: datetime, *, lock: bool = True
    ) -> RefreshToken | None:
        statement = select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        ).execution_options(populate_existing=True)
        return self._session.scalar(
            statement.with_for_update() if lock else statement
        )

    def active_session(self, session_id: UUID, user_id: UUID, now: datetime) -> bool:
        return self._session.scalar(select(RefreshToken.id).where(
            RefreshToken.id == session_id, RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now,
        )) is not None

    def revoke_refresh_token(
        self, token: RefreshToken, now: datetime, *, commit: bool = True
    ) -> None:
        token.revoked_at = now
        record_event(self._session, "session.revoked", token.id, actor_id=token.user_id)
        if commit:
            self._session.commit()

    def role(self, name: str) -> Role | None:
        return self._session.scalar(select(Role).where(Role.name == name))

    def revoke_user_sessions(self, user_id: UUID, now: datetime) -> None:
        self.lock_user(user_id)
        self._session.execute(update(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        ).values(revoked_at=now))
        record_event(self._session, "sessions.revoked", user_id)
        self._session.commit()

    def record_authentication_failure(self) -> None:
        record_event(self._session, "authentication.failed")
        self._session.commit()

    def list_users(self) -> list[User]:
        return list(self._session.scalars(select(User).order_by(User.created_at.desc())))
