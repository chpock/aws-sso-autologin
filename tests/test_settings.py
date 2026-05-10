"""Tests for runtime settings resolution."""

import logging
from pathlib import Path

from aws_sso_autologin.settings import RuntimeSettingsResolver


def test_resolver_uses_defaults_without_config_or_env():
    resolver = RuntimeSettingsResolver()

    settings = resolver.resolve(cli={})

    assert settings.log_level == "info"
    assert settings.log_format == "text"
    assert settings.safe_mode is False
    assert settings.tray_loss_behavior == "pause"


def test_resolver_reads_logging_from_config_file(tmp_path: Path):
    config_dir = tmp_path / "aws-sso-autologin"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        """
config_version: 1
logging:
  level: debug
  format: json
""".strip()
    )

    resolver = RuntimeSettingsResolver(config_path=config_file)
    settings = resolver.resolve(cli={})

    assert settings.log_level == "debug"
    assert settings.log_format == "json"


def test_resolver_cli_overrides_config_file(tmp_path: Path):
    config_dir = tmp_path / "aws-sso-autologin"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text(
        """
config_version: 1
logging:
  level: info
  format: text
""".strip()
    )

    resolver = RuntimeSettingsResolver(config_path=config_file)
    settings = resolver.resolve(cli={"log_level": "trace", "log_format": "json"})

    assert settings.log_level == "trace"
    assert settings.log_format == "json"


def test_logs_config_file_found(tmp_path: Path, caplog):
    config_dir = tmp_path / "aws-sso-autologin"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("logging:\n  level: debug\n")

    resolver = RuntimeSettingsResolver(config_path=config_file)

    with caplog.at_level(logging.INFO, logger="aws_sso_autologin.settings"):
        resolver.resolve(cli={})

    messages = [r.message for r in caplog.records]
    assert any("config file found" in m.lower() for m in messages), (
        f"Expected 'config file found' message, got: {messages}"
    )
    assert any(str(config_file) in m for m in messages), (
        f"Expected config path '{config_file}' in log, got: {messages}"
    )


def test_logs_setting_sources(tmp_path: Path, caplog):
    config_dir = tmp_path / "aws-sso-autologin"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("logging:\n  level: debug\n  format: json\n")

    resolver = RuntimeSettingsResolver(config_path=config_file)

    with caplog.at_level(logging.INFO, logger="aws_sso_autologin.settings"):
        resolver.resolve(cli={"log_level": "trace"})

    messages = [r.message for r in caplog.records]
    assert any("source: cli" in m.lower() for m in messages), (
        f"Expected 'source: cli' for log_level, got: {messages}"
    )
    assert any("source: config" in m.lower() for m in messages), (
        f"Expected 'source: config' for log_format, got: {messages}"
    )


def test_logs_no_config_file_when_missing(caplog):
    resolver = RuntimeSettingsResolver(
        config_path=Path("/nonexistent/path/config.yaml")
    )

    with caplog.at_level(logging.INFO, logger="aws_sso_autologin.settings"):
        resolver.resolve(cli={})

    messages = [r.message for r in caplog.records]
    assert any(
        "no config" in m.lower() or "not found" in m.lower() for m in messages
    ), f"Expected 'no config' or 'not found' message, got: {messages}"


def test_logs_default_source_without_config_or_cli(caplog):
    resolver = RuntimeSettingsResolver(
        config_path=Path("/nonexistent/path/config.yaml")
    )

    with caplog.at_level(logging.INFO, logger="aws_sso_autologin.settings"):
        resolver.resolve(cli={})

    messages = [r.message for r in caplog.records]
    assert any("source: default" in m.lower() for m in messages), (
        f"Expected 'source: default' messages, got: {messages}"
    )


def test_empty_env_log_level_falls_through(monkeypatch):
    monkeypatch.setenv("AWS_SSO_AUTOLOGIN_LOG_LEVEL", "")

    resolver = RuntimeSettingsResolver(
        config_path=Path("/nonexistent/path/config.yaml")
    )
    settings = resolver.resolve(cli={})

    assert settings.log_level == "info"


def test_empty_env_log_format_falls_through(monkeypatch):
    monkeypatch.setenv("AWS_SSO_AUTOLOGIN_LOG_FORMAT", "")

    resolver = RuntimeSettingsResolver(
        config_path=Path("/nonexistent/path/config.yaml")
    )
    settings = resolver.resolve(cli={})

    assert settings.log_format == "text"


def test_empty_env_tray_loss_behavior_falls_through(monkeypatch):
    monkeypatch.setenv("AWS_SSO_AUTOLOGIN_TRAY_LOSS_BEHAVIOR", "")

    resolver = RuntimeSettingsResolver(
        config_path=Path("/nonexistent/path/config.yaml")
    )
    settings = resolver.resolve(cli={})

    assert settings.tray_loss_behavior == "pause"


def test_empty_config_log_level_falls_through(tmp_path: Path):
    config_dir = tmp_path / "aws-sso-autologin"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("logging:\n  level: ''\n")

    resolver = RuntimeSettingsResolver(config_path=config_file)
    settings = resolver.resolve(cli={})

    assert settings.log_level == "info"


def test_empty_env_safe_mode_does_not_skip_config(monkeypatch, tmp_path: Path):
    """Empty env var must fall through to config, not short-circuit."""
    monkeypatch.setenv("AWS_SSO_AUTOLOGIN_SAFE_MODE", "")

    config_dir = tmp_path / "aws-sso-autologin"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("safe_mode: true\n")

    resolver = RuntimeSettingsResolver(config_path=config_file)
    settings = resolver.resolve(cli={})

    assert settings.safe_mode is True, (
        "Empty env should fall through to config safe_mode: true"
    )


def test_empty_config_safe_mode_treated_as_not_set(tmp_path: Path):
    """Empty string in config must fall through to default, not register as set."""
    config_dir = tmp_path / "aws-sso-autologin"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text("safe_mode: ''\n")

    resolver = RuntimeSettingsResolver(config_path=config_file)
    settings = resolver.resolve(cli={})

    assert settings.safe_mode is False


def test_config_safe_mode_truthy_string_resolves_true(tmp_path: Path):
    """Quoted truthy string like \"on\" must resolve to True via bool()."""
    config_dir = tmp_path / "aws-sso-autologin"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "config.yaml"
    config_file.write_text('safe_mode: "on"\n')

    resolver = RuntimeSettingsResolver(config_path=config_file)
    settings = resolver.resolve(cli={})

    assert settings.safe_mode is True, (
        'Quoted "on" in config should be truthy and resolve to True'
    )
