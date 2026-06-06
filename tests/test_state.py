"""Tests for persistent state storage."""

import json
from pathlib import Path

import pytest

from aws_sso_autologin.state import AppStateStore, default_state_path


def test_state_store_missing_file_defaults_to_running(tmp_path):
    store = AppStateStore(tmp_path / "state.json")

    assert store.is_global_monitoring_enabled() is True
    assert store.is_profile_monitoring_enabled("dev") is True


def test_state_store_persists_global_monitoring_state(tmp_path):
    path = tmp_path / "state" / "state.json"
    store = AppStateStore(path)

    store.set_global_monitoring_enabled(False)

    reloaded = AppStateStore(path)
    assert reloaded.is_global_monitoring_enabled() is False

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["global"]["monitoring"] == "paused"
    assert payload["global"]["updated_at"].endswith("Z")


def test_state_store_persists_profile_monitoring_state(tmp_path):
    path = tmp_path / "state" / "state.json"
    store = AppStateStore(path)

    store.set_profile_monitoring_enabled("dev", False)

    reloaded = AppStateStore(path)
    assert reloaded.is_profile_monitoring_enabled("dev") is False

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["profiles"]["dev"]["monitoring"] == "paused"
    assert payload["profiles"]["dev"]["updated_at"].endswith("Z")


def test_state_store_invalid_json_uses_empty_state(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not-json", encoding="utf-8")

    store = AppStateStore(path)

    assert store.is_profile_monitoring_enabled("dev") is True


def test_state_store_ignores_invalid_profile_entries(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profiles": {
                    "dev": "paused",
                    "prod": {"monitoring": "paused"},
                },
            }
        ),
        encoding="utf-8",
    )

    store = AppStateStore(path)

    assert store.is_profile_monitoring_enabled("dev") is True
    assert store.is_profile_monitoring_enabled("prod") is False

    store.set_profile_monitoring_enabled("dev", False)

    reloaded = AppStateStore(path)
    assert reloaded.is_profile_monitoring_enabled("dev") is False
    assert reloaded.is_profile_monitoring_enabled("prod") is False


def test_state_store_uses_private_permissions(tmp_path):
    path = tmp_path / "state" / "state.json"
    store = AppStateStore(path)

    store.set_profile_monitoring_enabled("dev", True)

    assert (path.parent.stat().st_mode & 0o777) == 0o700
    assert (path.stat().st_mode & 0o777) == 0o600


def test_state_store_ignores_symlink_state_file(tmp_path):
    real_path = tmp_path / "real.json"
    symlink_path = tmp_path / "state.json"
    real_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profiles": {"dev": {"monitoring": "paused"}},
            }
        ),
        encoding="utf-8",
    )
    symlink_path.symlink_to(real_path)

    store = AppStateStore(symlink_path)

    assert store.is_profile_monitoring_enabled("dev") is True

    with pytest.raises(OSError, match="Refusing to write state through symlinked"):
        store.set_profile_monitoring_enabled("dev", False)
    assert (
        json.loads(real_path.read_text(encoding="utf-8"))["profiles"]["dev"][
            "monitoring"
        ]
        == "paused"
    )


def test_state_store_ignores_symlinked_parent_directory(tmp_path):
    real_dir = tmp_path / "real-state-dir"
    real_dir.mkdir()
    real_path = real_dir / "state.json"
    real_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "profiles": {"dev": {"monitoring": "paused"}},
            }
        ),
        encoding="utf-8",
    )

    symlink_dir = tmp_path / "linked-state-dir"
    symlink_dir.symlink_to(real_dir, target_is_directory=True)
    symlink_path = symlink_dir / "state.json"

    store = AppStateStore(symlink_path)

    assert store.is_profile_monitoring_enabled("dev") is True

    with pytest.raises(OSError, match="Refusing to write state through symlinked"):
        store.set_profile_monitoring_enabled("dev", True)

    assert (
        json.loads(real_path.read_text(encoding="utf-8"))["profiles"]["dev"][
            "monitoring"
        ]
        == "paused"
    )


def test_default_state_path_uses_xdg_state_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert default_state_path() == tmp_path / "aws-sso-autologin" / "state.json"


def test_default_state_path_falls_back_to_local_state(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    assert (
        default_state_path() == tmp_path / ".local/state/aws-sso-autologin/state.json"
    )
