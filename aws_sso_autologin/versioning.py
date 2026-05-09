"""Helpers for release version computation from git tags."""

import re


_RELEASE_TAG_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_DESCRIBE_RE = re.compile(r"^(v\d+\.\d+\.\d+)-(\d+)-g([0-9a-fA-F]+)$")


def normalize_release_tag(tag: str) -> str:
    """Normalize a release tag `vX.Y.Z` to `X.Y.Z`."""
    match = _RELEASE_TAG_RE.match(tag.strip())
    if not match:
        raise ValueError(f"Unsupported release tag format: {tag!r}")
    major, minor, patch = match.groups()
    return f"{major}.{minor}.{patch}"


def build_version_from_describe(describe_output: str) -> str:
    """Build a PEP 440 version from `git describe --tags --long` output."""
    text = describe_output.strip()
    match = _DESCRIBE_RE.match(text)
    if not match:
        raise ValueError(f"Unsupported git describe format: {describe_output!r}")

    tag, commits_since_tag, commit_sha = match.groups()
    base_version = normalize_release_tag(tag)
    distance = int(commits_since_tag)

    if distance == 0:
        return base_version
    return f"{base_version}.dev{distance}+g{commit_sha.lower()}"
