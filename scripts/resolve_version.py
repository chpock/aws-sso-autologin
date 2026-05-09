#!/usr/bin/env python3
"""Resolve package version from nearest release tag."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from aws_sso_autologin.versioning import build_version_from_describe


def _git_describe() -> str:
    result = subprocess.run(
        [
            "git",
            "describe",
            "--tags",
            "--long",
            "--match",
            "v[0-9]*.[0-9]*.[0-9]*",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def write_embedded_version(version: str, output_path: Path) -> None:
    output_path.write_text(
        "\n".join(
            [
                '"""Auto-generated package version."""',
                "",
                f'__version__ = "{version}"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    output_arg = sys.argv[1] if len(sys.argv) > 1 else "aws_sso_autologin/_version.py"
    output_path = Path(output_arg)

    try:
        describe_output = _git_describe()
        version = build_version_from_describe(describe_output)
    except Exception:
        version = "0.0.0"

    write_embedded_version(version, output_path)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
