from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    verify_password,
)
from app.models import User
from app.repositories.users import UserRepository


class InvalidCredentialsError(Exception):
    pass


class AuthService:
    def __init__(self, users: UserRepository, settings: Settings) -> None:
        self._users = users
        self._settings = settings

    def authenticate(self, email: str, password: str) -> User:
        user = self._users.get_by_email(email)
        if user is None or not user.is_active or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError
        return user

    def issue_access_token(self, user: User) -> str:
        return create_access_token(user.id, self._settings)

    def issue_token_pair(self, user: User) -> tuple[str, str]:
        refresh_token = create_refresh_token()
        self._users.create_refresh_token(
            user,
            hash_token(refresh_token),
            datetime.now(timezone.utc) + timedelta(days=self._settings.refresh_token_expire_days),
        )
        return self.issue_access_token(user), refresh_token

    def rotate_refresh_token(self, raw_token: str) -> tuple[str, str]:
        now = datetime.now(timezone.utc)
        token = self._users.get_active_refresh_token(hash_token(raw_token), now)
        if token is None:
            raise InvalidCredentialsError
        user = self._users.get_by_id(token.user_id)
        if user is None or not user.is_active:
            raise InvalidCredentialsError
        self._users.revoke_refresh_token(token, now)
        return self.issue_token_pair(user)

    def revoke_refresh_token(self, raw_token: str) -> None:
        token = self._users.get_active_refresh_token(
            hash_token(raw_token), datetime.now(timezone.utc)
        )
        if token is not None:
            self._users.revoke_refresh_token(token, datetime.now(timezone.utc))

    @property
    def refresh_token_max_age_seconds(self) -> int:
        return self._settings.refresh_token_expire_days * 24 * 60 * 60
