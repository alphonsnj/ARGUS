from uuid import uuid4

import jwt

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)


def settings() -> Settings:
    return Settings(
        database_url="postgresql+psycopg://argus:argus@localhost/argus",
        redis_url="redis://localhost:6379/0",
        s3_endpoint_url="http://localhost:9000",
        s3_access_key="argus-local",
        s3_secret_key="a" * 32,
        jwt_secret_key="a" * 64,
    )


def test_password_round_trip() -> None:
    password_hash = hash_password("correct-horse-battery-staple")
    assert verify_password("correct-horse-battery-staple", password_hash)
    assert not verify_password("incorrect-password", password_hash)


def test_access_token_has_bound_claims() -> None:
    config = settings()
    token = create_access_token(uuid4(), config)
    claims = jwt.decode(
        token,
        config.jwt_secret_key.get_secret_value(),
        algorithms=["HS256"],
        audience=config.jwt_audience,
        issuer=config.jwt_issuer,
    )
    assert claims["sub"]


def test_access_token_can_be_decoded_to_its_subject() -> None:
    config = settings()
    subject = uuid4()
    assert decode_access_token(create_access_token(subject, config), config) == subject


def test_refresh_tokens_are_random_and_only_their_digest_is_storable() -> None:
    first_token = create_refresh_token()
    second_token = create_refresh_token()
    assert first_token != second_token
    assert hash_token(first_token) != first_token
    assert len(hash_token(first_token)) == 64


def test_cors_origins_match_browser_origin_header() -> None:
    config = Settings(
        database_url="postgresql+psycopg://argus:argus@localhost/argus",
        redis_url="redis://localhost:6379/0",
        s3_endpoint_url="http://localhost:9000",
        s3_access_key="argus-local",
        s3_secret_key="a" * 32,
        jwt_secret_key="a" * 64,
        cors_origins=["http://localhost:3000"],
    )
    assert config.cors_origin_strings == ["http://localhost:3000"]
