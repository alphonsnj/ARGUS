from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.security_middleware import security_boundary


def test_production_rejects_insecure_settings() -> None:
    values = get_settings().model_dump()
    values.update(app_env="production", cookie_secure=False)
    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        type(get_settings())(**values)
    values.update(cookie_secure=True, cors_origins=["http://example.com"])
    with pytest.raises(ValueError, match="HTTPS"):
        type(get_settings())(**values)


def test_production_rate_limit_and_unavailability_fail_closed() -> None:
    from redis.exceptions import ConnectionError

    settings = get_settings().model_copy(update={"app_env": "production"})
    app = FastAPI()
    app.middleware("http")(security_boundary)

    @app.post("/api/v1/auth/token")
    def endpoint() -> dict[str, bool]:
        return {"called": True}

    redis = AsyncMock()
    with (
        patch("app.security_middleware.get_settings", return_value=settings),
        patch("app.security_middleware.Redis.from_url", return_value=redis),
    ):
        client = TestClient(app)
        redis.eval.return_value = 1
        assert client.post("/api/v1/auth/token").status_code == 200
        redis.eval.return_value = settings.auth_rate_limit_per_minute + 1
        limited = client.post("/api/v1/auth/token")
        assert limited.status_code == 429
        assert limited.headers["Retry-After"] == "60"
        assert limited.headers["Cache-Control"] == "no-store"
        redis.eval.side_effect = ConnectionError("offline")
        assert client.post("/api/v1/auth/token").status_code == 503
