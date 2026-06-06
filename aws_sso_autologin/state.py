"""Persistent application state storage."""

import json
import os
import tempfile
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aws_sso_autologin.logger import get_logger

logger = get_logger(__name__)

STATE_SCHEMA_VERSION = 1
MONITORING_RUNNING = "running"
MONITORING_PAUSED = "paused"


class StateStore(ABC):
    """Profile monitoring state persistence contract."""

    @abstractmethod
    def is_global_monitoring_enabled(self) -> bool:
        """Return whether global monitoring should run."""

    @abstractmethod
    def set_global_monitoring_enabled(self, enabled: bool) -> None:
        """Persist global monitoring state."""

    @abstractmethod
    def is_profile_monitoring_enabled(self, profile_name: str) -> bool:
        """Return whether monitoring should run for a profile."""

    @abstractmethod
    def set_profile_monitoring_enabled(self, profile_name: str, enabled: bool) -> None:
        """Persist monitoring state for a profile."""


class MemoryStateStore(StateStore):
    """In-memory state store used by tests and embedded callers by default."""

    def __init__(self) -> None:
        self._monitoring_enabled = True
        self._profiles: dict[str, bool] = {}

    def is_global_monitoring_enabled(self) -> bool:
        return self._monitoring_enabled

    def set_global_monitoring_enabled(self, enabled: bool) -> None:
        self._monitoring_enabled = enabled

    def is_profile_monitoring_enabled(self, profile_name: str) -> bool:
        return self._profiles.get(profile_name, True)

    def set_profile_monitoring_enabled(self, profile_name: str, enabled: bool) -> None:
        self._profiles[profile_name] = enabled


class AppStateStore(StateStore):
    """JSON-backed state store for persisted per-profile runtime state."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_state_path()
        self._state = self._load()

    @property
    def path(self) -> Path:
        return self._path

    def is_global_monitoring_enabled(self) -> bool:
        global_state = self._state.get("global", {})
        if not isinstance(global_state, dict):
            return True
        return global_state.get("monitoring") != MONITORING_PAUSED

    def set_global_monitoring_enabled(self, enabled: bool) -> None:
        global_state = self._state.setdefault("global", {})
        if not isinstance(global_state, dict):
            global_state = {}
        self._state["global"] = {
            **global_state,
            "monitoring": MONITORING_RUNNING if enabled else MONITORING_PAUSED,
            "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        self._write()

    def is_profile_monitoring_enabled(self, profile_name: str) -> bool:
        profile = self._state.get("profiles", {}).get(profile_name, {})
        if not isinstance(profile, dict):
            return True
        return profile.get("monitoring") != MONITORING_PAUSED

    def set_profile_monitoring_enabled(self, profile_name: str, enabled: bool) -> None:
        profiles = self._state.setdefault("profiles", {})
        existing = profiles.get(profile_name, {})
        if not isinstance(existing, dict):
            existing = {}
        profiles[profile_name] = {
            **existing,
            "monitoring": MONITORING_RUNNING if enabled else MONITORING_PAUSED,
            "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        self._write()

    def _load(self) -> dict[str, Any]:
        symlink_component = _find_symlink_path_component(self._path)
        if symlink_component is not None:
            logger.warning(
                "state path contains a symlink; ignoring persisted state",
                extra={
                    "event": "state_file_symlink_ignored",
                    "path": str(self._path),
                    "symlink_path": str(symlink_component),
                },
            )
            return _empty_state()

        if not self._path.exists():
            return _empty_state()

        try:
            with self._path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.warning(
                "state file could not be loaded; using empty state",
                extra={
                    "event": "state_file_load_failed",
                    "path": str(self._path),
                    "error": str(exc),
                },
            )
            return _empty_state()

        if not isinstance(payload, dict):
            logger.warning(
                "state file has invalid root object; using empty state",
                extra={"event": "state_file_invalid", "path": str(self._path)},
            )
            return _empty_state()

        if payload.get("schema_version") != STATE_SCHEMA_VERSION:
            logger.warning(
                "state file schema is unsupported; using empty state",
                extra={
                    "event": "state_file_unsupported_schema",
                    "path": str(self._path),
                    "schema_version": payload.get("schema_version"),
                },
            )
            return _empty_state()

        global_state = payload.get("global", {})
        if not isinstance(global_state, dict):
            logger.warning(
                "state file global section is invalid; ignoring global state",
                extra={"event": "state_file_global_invalid", "path": str(self._path)},
            )
            global_state = {}

        profiles = payload.get("profiles")
        if not isinstance(profiles, dict):
            logger.warning(
                "state file profiles section is invalid; using empty state",
                extra={"event": "state_file_profiles_invalid", "path": str(self._path)},
            )
            return _empty_state()

        sanitized_profiles: dict[str, dict[str, Any]] = {}
        for profile_name, profile_state in profiles.items():
            if not isinstance(profile_state, dict):
                logger.warning(
                    "state file profile entry is invalid; ignoring profile state",
                    extra={
                        "event": "state_file_profile_entry_invalid",
                        "path": str(self._path),
                        "profile": str(profile_name),
                    },
                )
                continue
            sanitized_profiles[str(profile_name)] = profile_state

        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "global": global_state,
            "profiles": sanitized_profiles,
        }

    def _write(self) -> None:
        symlink_component = _find_symlink_path_component(self._path)
        if symlink_component is not None:
            error = (
                "Refusing to write state through symlinked path component: "
                f"{symlink_component}"
            )
            logger.warning(
                "state path contains a symlink; refusing to write state",
                extra={
                    "event": "state_file_symlink_write_refused",
                    "path": str(self._path),
                    "symlink_path": str(symlink_component),
                    "error": error,
                },
            )
            raise OSError(error)

        self._path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._path.parent.chmod(0o700)

        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self._path.name}.", suffix=".tmp", dir=self._path.parent
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._state, handle, indent=2, sort_keys=True)
                handle.write("\n")
            temp_path.chmod(0o600)
            temp_path.replace(self._path)
            self._path.chmod(0o600)
            logger.debug(
                "state file written",
                extra={"event": "state_file_written", "path": str(self._path)},
            )
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise


def default_state_path() -> Path:
    """Return the production state file path."""

    state_home = os.getenv("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else Path.home() / ".local/state"
    return base / "aws-sso-autologin" / "state.json"


def _find_symlink_path_component(path: Path) -> Path | None:
    for candidate in (path, *path.parents):
        if candidate.is_symlink():
            return candidate
    return None


def _empty_state() -> dict[str, Any]:
    return {"schema_version": STATE_SCHEMA_VERSION, "global": {}, "profiles": {}}
