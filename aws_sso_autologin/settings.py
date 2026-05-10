"""Runtime settings resolution from layered sources."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from aws_sso_autologin.logger import get_logger

logger = get_logger(__name__)
# Ensure settings resolution logs are visible even before configure_logging()
# runs in main().  The root logger defaults to WARNING at import time, so
# the per-module handler created by get_logger mirrors that level and would
# silently drop INFO messages emitted during resolve().
logger.setLevel(logging.INFO)
for _h in logger.handlers:
    _h.setLevel(logging.INFO)


@dataclass(frozen=True)
class RuntimeSettings:
    """Resolved runtime settings."""

    log_level: str = "info"
    log_format: str = "text"
    safe_mode: bool = False
    tray_loss_behavior: str = "pause"


class RuntimeSettingsResolver:
    """Resolves runtime settings from defaults/config/env/CLI."""

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or self._default_config_path()

    def resolve(self, cli: dict[str, Any]) -> RuntimeSettings:
        config = self._load_config()

        log_level, ll_source = self._resolve_log_level(config, cli)
        log_format, lf_source = self._resolve_log_format(config, cli)
        safe_mode, sm_source = self._resolve_safe_mode(config, cli)
        tray_loss_behavior, tlb_source = self._resolve_tray_loss_behavior(config, cli)

        logger.info(
            "Settings applied: log_level=%s (source: %s)",
            log_level,
            ll_source,
        )
        logger.info(
            "Settings applied: log_format=%s (source: %s)",
            log_format,
            lf_source,
        )
        logger.info(
            "Settings applied: safe_mode=%s (source: %s)",
            safe_mode,
            sm_source,
        )
        logger.info(
            "Settings applied: tray_loss_behavior=%s (source: %s)",
            tray_loss_behavior,
            tlb_source,
        )

        return RuntimeSettings(
            log_level=log_level,
            log_format=log_format,
            safe_mode=safe_mode,
            tray_loss_behavior=tray_loss_behavior,
        )

    def _resolve_log_level(
        self, config: dict[str, Any], cli: dict[str, Any]
    ) -> tuple[str, str]:
        cli_val = cli.get("log_level")
        if cli_val:
            return str(cli_val).strip().lower(), "cli"
        env_val = os.getenv("AWS_SSO_AUTOLOGIN_LOG_LEVEL")
        if env_val is not None and env_val.strip():
            return env_val.strip().lower(), "env"
        config_val = config.get("logging", {}).get("level")
        if config_val is not None and str(config_val).strip():
            return str(config_val).strip().lower(), "config"
        return "info", "default"

    def _resolve_log_format(
        self, config: dict[str, Any], cli: dict[str, Any]
    ) -> tuple[str, str]:
        cli_val = cli.get("log_format")
        if cli_val:
            return str(cli_val).strip().lower(), "cli"
        env_val = os.getenv("AWS_SSO_AUTOLOGIN_LOG_FORMAT")
        if env_val is not None and env_val.strip():
            return env_val.strip().lower(), "env"
        config_val = config.get("logging", {}).get("format")
        if config_val is not None and str(config_val).strip():
            return str(config_val).strip().lower(), "config"
        return "text", "default"

    def _resolve_safe_mode(
        self, config: dict[str, Any], cli: dict[str, Any]
    ) -> tuple[bool, str]:
        if cli.get("safe_mode") is True:
            return True, "cli"
        env_value = os.getenv("AWS_SSO_AUTOLOGIN_SAFE_MODE")
        if env_value is not None and env_value.strip():
            return env_value.strip() == "1", "env"
        safe_mode_val = config.get("safe_mode")
        if safe_mode_val is not None and str(safe_mode_val).strip():
            return bool(safe_mode_val), "config"
        return False, "default"

    def _resolve_tray_loss_behavior(
        self, config: dict[str, Any], cli: dict[str, Any]
    ) -> tuple[str, str]:
        cli_val = cli.get("tray_loss_behavior")
        if cli_val:
            return str(cli_val).strip().lower(), "cli"
        env_val = os.getenv("AWS_SSO_AUTOLOGIN_TRAY_LOSS_BEHAVIOR")
        if env_val is not None and env_val.strip():
            return env_val.strip().lower(), "env"
        config_val = config.get("tray_loss_behavior")
        if config_val is not None and str(config_val).strip():
            return str(config_val).strip().lower(), "config"
        return "pause", "default"

    def _default_config_path(self) -> Path:
        xdg = os.getenv("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg) / "aws-sso-autologin" / "config.yaml"
        return Path.home() / ".config" / "aws-sso-autologin" / "config.yaml"

    def _load_config(self) -> dict[str, Any]:
        if not self._config_path.exists():
            logger.info("No config file found at %s", self._config_path)
            return {}

        logger.info("Config file found: %s", self._config_path)

        with self._config_path.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}

        if not isinstance(loaded, dict):
            return {}
        return loaded
