import pytest
from fastapi.testclient import TestClient

from dayz.services import api


def test_auth_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "API_AUTH_DISABLED", False)
    monkeypatch.setattr(api, "API_TOKEN", "")

    with pytest.raises(RuntimeError, match="API_TOKEN must be set"):
        api.validate_auth_configuration()


def test_application_startup_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "API_AUTH_DISABLED", False)
    monkeypatch.setattr(api, "API_TOKEN", "")

    with pytest.raises(RuntimeError, match="API_TOKEN must be set"), TestClient(api.app):
        pass


def test_auth_configuration_allows_explicit_development_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "API_AUTH_DISABLED", True)
    monkeypatch.setattr(api, "API_TOKEN", "")

    api.validate_auth_configuration()


def test_health_is_public_but_verify_requires_valid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "API_AUTH_DISABLED", False)
    monkeypatch.setattr(api, "API_TOKEN", "test-token")

    with TestClient(api.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/auth/verify").status_code == 401
        assert (
            client.get("/auth/verify", headers={"Authorization": "Bearer wrong"}).status_code == 401
        )
        response = client.get("/auth/verify", headers={"Authorization": "Bearer test-token"})

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}


def test_placeholder_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "API_AUTH_DISABLED", False)
    monkeypatch.setattr(api, "API_TOKEN", "your-secret-token-here")

    with pytest.raises(RuntimeError, match="API_TOKEN must be set"):
        api.validate_auth_configuration()


def test_status_is_protected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "API_AUTH_DISABLED", False)
    monkeypatch.setattr(api, "API_TOKEN", "test-token")

    with TestClient(api.app) as client:
        response = client.get("/status")

    assert response.status_code == 401


def test_raw_configuration_uses_shared_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "API_AUTH_DISABLED", False)
    monkeypatch.setattr(api, "API_TOKEN", "test-token")

    with TestClient(api.app) as client:
        response = client.get("/config", params={"raw": "true"})

    assert response.status_code == 401
