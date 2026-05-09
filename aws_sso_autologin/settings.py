"""Runtime settings resolution from layered sources."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass(frozen=True)
class RuntimeSettings:
    """Resolved runtime settings."""

    log_level: str = "info"
    log_format: str = "text"
    safe_mode: bool = False
    tray_loss_behavior: str = "pause"


class RuntimeSettingsResolver:
    """Resolves runtime settings from defaults/config/env/CLI."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = config_path or self._default_config_path()

    def resolve(self, cli: dict[str, Any]) -> RuntimeSettings:
        config = self._load_config()

        log_level = self._resolve_log_level(config, cli)
        log_format = self._resolve_log_format(config, cli)
        safe_mode = self._resolve_safe_mode(config, cli)
        tray_loss_behavior = self._resolve_tray_loss_behavior(config, cli)

        return RuntimeSettings(
            log_level=log_level,
            log_format=log_format,
            safe_mode=safe_mode,
            tray_loss_behavior=tray_loss_behavior,
        )

    def _resolve_log_level(self, config: dict[str, Any], cli: dict[str, Any]) -> str:
        value = (
            cli.get("log_level")
            or os.getenv("AWS_SSO_AUTOLOGIN_LOG_LEVEL")
            or config.get("logging", {}).get("level")
            or "info"
        )
        return str(value).strip().lower()

    def _resolve_log_format(self, config: dict[str, Any], cli: dict[str, Any]) -> str:
        value = (
            cli.get("log_format")
            or os.getenv("AWS_SSO_AUTOLOGIN_LOG_FORMAT")
            or config.get("logging", {}).get("format")
            or "text"
        )
        return str(value).strip().lower()

    def _resolve_safe_mode(self, config: dict[str, Any], cli: dict[str, Any]) -> bool:
        if cli.get("safe_mode") is True:
            return True

        env_value = os.getenv("AWS_SSO_AUTOLOGIN_SAFE_MODE")
        if env_value is not None:
            return env_value.strip() == "1"

        return bool(config.get("safe_mode", False))

    def _resolve_tray_loss_behavior(self, config: dict[str, Any], cli: dict[str, Any]) -> str:
        value = (
            cli.get("tray_loss_behavior")
            or os.getenv("AWS_SSO_AUTOLOGIN_TRAY_LOSS_BEHAVIOR")
            or config.get("tray_loss_behavior")
            or "pause"
        )
        return str(value).strip().lower()

    def _default_config_path(self) -> Path:
        xdg = os.getenv("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg) / "aws-sso-autologin" / "config.yaml"
        return Path.home() / ".config" / "aws-sso-autologin" / "config.yaml"

    def _load_config(self) -> dict[str, Any]:
        if not self._config_path.exists():
            return {}

        with self._config_path.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}

        if not isinstance(loaded, dict):
            return {}
        return loaded
