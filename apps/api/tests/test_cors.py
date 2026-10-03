from fastapi.testclient import TestClient

from app.main import app, settings


def test_session_revocation_preflight_allows_configured_browser() -> None:
    origin = settings.cors_origin_strings[0]
    with TestClient(app) as client:
        response = client.options("/api/v1/users/example/sessions", headers={
            "Origin": origin,
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization",
        })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "DELETE" in response.headers["access-control-allow-methods"]


def test_session_revocation_preflight_rejects_untrusted_browser() -> None:
    with TestClient(app) as client:
        response = client.options("/api/v1/users/example/sessions", headers={
            "Origin": "https://untrusted.invalid",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "authorization",
        })
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
