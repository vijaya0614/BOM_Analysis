import pytest

from src import auth
from src.api.main import app
from src.config import Settings, settings


def test_default_bootstrap_does_not_create_shared_demo_passwords(monkeypatch):
    monkeypatch.setattr(settings, "JWT_DEMO_USER", "")
    monkeypatch.setattr(settings, "JWT_DEMO_PASSWORD", type(settings.JWT_DEMO_PASSWORD)(""))
    monkeypatch.setattr(settings, "JWT_REVIEWER_PASSWORD", type(settings.JWT_REVIEWER_PASSWORD)(""))
    monkeypatch.setattr(settings, "JWT_AUDITOR_PASSWORD", type(settings.JWT_AUDITOR_PASSWORD)(""))
    assert auth._bootstrap_users() == {}


def test_production_requires_explicit_strong_jwt_secret(monkeypatch):
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "")
    monkeypatch.setattr(settings, "ENV", "production")
    with pytest.raises(RuntimeError, match="must be configured"):
        auth.jwt_secret()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "short")
    with pytest.raises(RuntimeError, match="at least 32"):
        auth.jwt_secret()


def test_cors_rejects_wildcard_origin():
    with pytest.raises(ValueError, match="cannot contain '*'"):
        Settings(CORS_ORIGINS=["*"])


def test_unified_legacy_routes_do_not_require_a_login():
    compatibility_routes = [
        route for route in app.routes
        if getattr(route, "endpoint", None)
        and route.endpoint.__module__ == "src.api.compat"
    ]
    assert compatibility_routes
    assert all(not route.dependencies for route in compatibility_routes)
    assert not any(getattr(route, "path", "") == "/auth/login" for route in app.routes)
    assert app.state.limiter is not None


def test_unified_api_keeps_request_and_upload_size_limits():
    from src.api import main as api_main
    from src.industry_data.http_routes import MAX_UPLOAD_BYTES

    assert api_main.MAX_REQUEST_BYTES == 70 * 1024 * 1024
    assert MAX_UPLOAD_BYTES == 50 * 1024 * 1024
