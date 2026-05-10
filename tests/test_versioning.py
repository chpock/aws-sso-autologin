"""Tests for git tag-based version computation helpers."""

import pytest

from aws_sso_autologin.versioning import (
    build_version_from_describe,
    normalize_release_tag,
)


def test_normalize_release_tag_accepts_v_prefix():
    assert normalize_release_tag("v1.2.3") == "1.2.3"


def test_normalize_release_tag_rejects_invalid_format():
    with pytest.raises(ValueError):
        normalize_release_tag("1.2.3")


def test_build_version_from_describe_returns_release_version_at_tag():
    assert build_version_from_describe("v1.2.3-0-gabc1234") == "1.2.3"


def test_build_version_from_describe_returns_dev_version_between_tags():
    assert build_version_from_describe("v1.2.3-4-gabc1234") == "1.2.3.dev4+gabc1234"
