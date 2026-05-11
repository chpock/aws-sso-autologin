#!/bin/sh

set -e

SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"

[ -d "$SCRIPT_DIR/.venv" ] || make -C "$SCRIPT_DIR" venv
[ -d "$(echo "$SCRIPT_DIR/.venv/lib"/python*/"site-packages/PySide6")" ] || make -C "$SCRIPT_DIR" prepare

. "$SCRIPT_DIR"/.venv/bin/activate

exec python -m aws_sso_autologin
