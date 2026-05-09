"""Tests for application version resolution."""

import importlib
import sys


def _reload_package() -> object:
    sys.modules.pop("aws_sso_autologin", None)
    return importlib.import_module("aws_sso_autologin")


def test_version_defaults_to_zero_without_embedded_module():
    sys.modules.pop("aws_sso_autologin._version", None)

    package = _reload_package()

    assert package.__version__ == "0.0.0"
    assert package.VERSION_SOURCE == "default"


def test_version_uses_embedded_module_when_available(monkeypatch):
    module = type(sys)("aws_sso_autologin._version")
    module.__version__ = "1.2.3"
    monkeypatch.setitem(sys.modules, "aws_sso_autologin._version", module)

    package = _reload_package()

    assert package.__version__ == "1.2.3"
    assert package.VERSION_SOURCE == "embedded"
