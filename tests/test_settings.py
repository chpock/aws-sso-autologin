"""Tests for runtime settings resolution."""

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
