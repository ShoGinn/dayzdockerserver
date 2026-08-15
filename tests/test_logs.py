from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dayz.core import server as server_module
from dayz.core.server import ServerManager, resolve_profile_log_file
from dayz.services import api


def configure_profiles(monkeypatch: pytest.MonkeyPatch, profiles: Path) -> None:
    monkeypatch.setattr(server_module, "PROFILES_DIR", profiles)


def test_resolver_accepts_regular_profile_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    configure_profiles(monkeypatch, tmp_path)
    log_file = tmp_path / "server.RPT"
    log_file.write_text("ready")

    assert resolve_profile_log_file("server.RPT") == log_file.resolve()


@pytest.mark.parametrize("filename", ["/etc/passwd", "../secret.log", "nested/../../secret.log"])
def test_resolver_rejects_absolute_and_traversal_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, filename: str
) -> None:
    configure_profiles(monkeypatch, tmp_path)

    with pytest.raises(ValueError):
        resolve_profile_log_file(filename)


def test_resolver_rejects_symlink_that_escapes_profiles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    secret = tmp_path / "secret.log"
    secret.write_text("secret")
    (profiles / "escape.log").symlink_to(secret)
    configure_profiles(monkeypatch, profiles)

    with pytest.raises(ValueError):
        resolve_profile_log_file("escape.log")


def test_resolver_rejects_directories(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_profiles(monkeypatch, tmp_path)
    (tmp_path / "logs").mkdir()

    with pytest.raises(ValueError):
        resolve_profile_log_file("logs")


def test_resolver_reports_missing_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_profiles(monkeypatch, tmp_path)

    with pytest.raises(FileNotFoundError):
        resolve_profile_log_file("missing.log")


def test_tail_reads_only_requested_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configure_profiles(monkeypatch, tmp_path)
    (tmp_path / "server.log").write_bytes(b"0123456789")

    success, _, content = ServerManager().read_log_tail("server.log", 4)

    assert success is True
    assert content == "6789"


@pytest.mark.parametrize("bytes_count", [0, 524289])
def test_tail_rejects_out_of_range_byte_counts(bytes_count: int) -> None:
    with pytest.raises(ValueError, match="bytes_count"):
        ServerManager().read_log_tail("server.log", bytes_count)


def test_log_endpoints_reject_unsafe_paths_and_oversized_tails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(api, "API_AUTH_DISABLED", False)
    monkeypatch.setattr(api, "API_TOKEN", "test-token")
    headers = {"Authorization": "Bearer test-token"}

    with TestClient(api.app) as client:
        traversal = client.get("/logs", params={"filename": "../secret"}, headers=headers)
        stream = client.get("/logs/stream", params={"filename": "/etc/passwd"}, headers=headers)
        oversized = client.get(
            "/logs", params={"filename": "server.log", "bytes_count": 524289}, headers=headers
        )

    assert traversal.status_code == 400
    assert stream.status_code == 400
    assert oversized.status_code == 422
