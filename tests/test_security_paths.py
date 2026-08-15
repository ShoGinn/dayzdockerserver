import stat
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from dayz.config.models import BulkModRequest, ServerConfig, ServerState
from dayz.core import mods as mods_module
from dayz.core import server as server_module
from dayz.core.mods import ModManager
from dayz.core.server import ServerManager
from dayz.mods import vpp
from dayz.utils.steam_id import validate_workshop_id


class StoppedControl:
    def get_state(self) -> SimpleNamespace:
        return SimpleNamespace(state=ServerState.STOPPED.value)


def build_server_manager() -> ServerManager:
    manager = ServerManager.__new__(ServerManager)
    manager.control = StoppedControl()
    return manager


@pytest.mark.parametrize(
    "mod_id",
    ["../profiles", "123/../../profiles", "/serverfiles", "123 +quit"],
)
def test_mod_paths_reject_non_numeric_workshop_ids(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mod_id: str
) -> None:
    monkeypatch.setattr(mods_module, "WORKSHOP_DIR", tmp_path / "workshop")
    manager = ModManager.__new__(ModManager)

    with pytest.raises(ValueError, match="Workshop ID"):
        manager._get_mod_dir(mod_id)


def test_bulk_mod_request_rejects_unsafe_workshop_ids() -> None:
    with pytest.raises(ValidationError, match="Workshop IDs"):
        BulkModRequest(mod_ids=["123", "../../profiles"])


def test_workshop_id_is_canonicalized_through_integer_conversion() -> None:
    assert validate_workshop_id("000123") == "123"

    with pytest.raises(ValueError, match="greater than zero"):
        validate_workshop_id("0")


def test_mod_name_rejects_path_separators(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    workshop = tmp_path / "workshop"
    mod_dir = workshop / "123"
    mod_dir.mkdir(parents=True)
    (mod_dir / "meta.cpp").write_text('name = "unsafe/../../../profiles";')
    monkeypatch.setattr(mods_module, "WORKSHOP_DIR", workshop)
    manager = ModManager.__new__(ModManager)

    assert manager._get_mod_name("123") is None


def test_mod_name_rejects_meta_symlink_outside_workshop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workshop = tmp_path / "workshop"
    mod_dir = workshop / "123"
    mod_dir.mkdir(parents=True)
    outside_meta = tmp_path / "outside-meta.cpp"
    outside_meta.write_text('name = "Outside";')
    (mod_dir / "meta.cpp").symlink_to(outside_meta)
    monkeypatch.setattr(mods_module, "WORKSHOP_DIR", workshop)
    manager = ModManager.__new__(ModManager)

    assert manager._get_mod_name("123") is None


def test_mod_keys_reject_directory_symlink_outside_workshop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workshop = tmp_path / "workshop"
    mod_dir = workshop / "123"
    mod_dir.mkdir(parents=True)
    outside_keys = tmp_path / "outside-keys"
    outside_keys.mkdir()
    (mod_dir / "keys").symlink_to(outside_keys, target_is_directory=True)
    monkeypatch.setattr(mods_module, "WORKSHOP_DIR", workshop)
    manager = ModManager.__new__(ModManager)

    assert manager._get_mod_keys_dir("123") is None


def test_mod_keys_ignore_key_file_symlink_outside_workshop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    workshop = tmp_path / "workshop"
    keys_dir = workshop / "123" / "keys"
    keys_dir.mkdir(parents=True)
    outside_key = tmp_path / "outside.bikey"
    outside_key.write_text("key")
    (keys_dir / "escape.bikey").symlink_to(outside_key)
    server_keys = tmp_path / "server-keys"
    monkeypatch.setattr(mods_module, "WORKSHOP_DIR", workshop)
    monkeypatch.setattr(mods_module, "SERVER_KEYS_DIR", server_keys)
    manager = ModManager.__new__(ModManager)

    assert manager._symlink_mod_keys("123") is True
    assert list(server_keys.iterdir()) == []


@pytest.mark.parametrize(
    "storage_name",
    ["../storage_1", "storage_1/../../../outside", "/tmp/storage_1", "storage_1\\other"],
)
def test_wipe_storage_rejects_escaping_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, storage_name: str
) -> None:
    active = tmp_path / "active"
    (active / "dayzOffline.chernarusplus").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep")
    monkeypatch.setattr(server_module, "MPMISSIONS_ACTIVE", active)
    manager = build_server_manager()
    monkeypatch.setattr(manager, "_get_map_name", lambda: "dayzOffline.chernarusplus")

    success, message = manager.wipe_storage(storage_name)

    assert success is False
    assert message == "Invalid storage directory name"
    assert marker.read_text() == "keep"


def test_wipe_storage_rejects_escaping_mission_template(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    active = tmp_path / "active"
    active.mkdir()
    monkeypatch.setattr(server_module, "MPMISSIONS_ACTIVE", active)
    manager = build_server_manager()
    monkeypatch.setattr(manager, "_get_map_name", lambda: "../../outside")

    success, message = manager.wipe_storage("storage_1")

    assert success is False
    assert message == "Invalid mission template"


def test_config_parse_error_does_not_expose_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_file = tmp_path / "serverDZ.cfg"
    config_file.write_text("invalid")
    monkeypatch.setattr(server_module, "SERVER_CFG", config_file)

    def fail_parse(cls: type[ServerConfig], path: Path) -> ServerConfig:
        raise RuntimeError(f"secret path: {path}")

    monkeypatch.setattr(ServerConfig, "from_cfg_file", classmethod(fail_parse))
    manager = ServerManager.__new__(ServerManager)

    success, message, config = manager.get_server_config()

    assert success is False
    assert message == "Failed to parse server configuration"
    assert str(config_file) not in message
    assert config is None


def test_vpp_password_file_is_owner_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    credentials = tmp_path / "VPPAdminTools" / "Permissions" / "credentials.txt"
    monkeypatch.setattr(vpp, "CREDS_PATH", credentials)

    success, message = vpp.set_password("sensitive-password")

    assert success is True
    assert message == "VPP password set"
    assert credentials.read_text() == "sensitive-password\n"
    assert stat.S_IMODE(credentials.stat().st_mode) == 0o600


def test_vpp_password_write_replaces_symlink_without_following_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    credentials = tmp_path / "VPPAdminTools" / "Permissions" / "credentials.txt"
    credentials.parent.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("keep")
    credentials.symlink_to(outside)
    monkeypatch.setattr(vpp, "CREDS_PATH", credentials)

    success, _ = vpp.set_password("replacement")

    assert success is True
    assert credentials.is_symlink() is False
    assert credentials.read_text() == "replacement\n"
    assert outside.read_text() == "keep"
