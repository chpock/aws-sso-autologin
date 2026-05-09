# AGENTS.md

## Fast start (use these, do not guess)
- `make prepare` - create `.venv` (if missing), upgrade pip, install `requirements.txt`.
- `make test` - run full test suite via `.venv/bin/pytest`.
- `make test-verbose` - same with `-v`.
- `make run` - run app as `python -m aws_sso_autologin` from `.venv`.

## Focused verification
- Single test file: `.venv/bin/pytest tests/test_service.py -q`
- Single test: `.venv/bin/pytest tests/test_service.py::test_check_tray_host_available_true_for_hyprland -q`

## Runtime behavior that is easy to misread
- `make run` can exit with code 1 before UI startup if tray-host preflight fails.
- For that failure, trust structured stdout logs first:
  - `event=tray_host_unavailable_unknown` or `event=tray_host_unavailable_protocol_mismatch` (from `aws_sso_autologin/service.py`)
  - `event=tray_host_preflight_failed` (from `aws_sso_autologin/__main__.py`)
- On Hyprland, detection is mapped as `TrayHostType.GENERIC` and considered StatusNotifier-capable in current code.

## Real entrypoints and boundaries
- App entrypoint: `aws_sso_autologin.__main__:main` (also wired as script `aws-sso-autologin` in `pyproject.toml`).
- Tray-host detection/preflight logic: `aws_sso_autologin/service.py`.
- Main runtime orchestration (Qt init, preflight, operators, event loop): `aws_sso_autologin/__main__.py`.

## Test environment quirks
- Tray/UI tests instantiate real `QApplication` (`tests/test_tray.py`); if PySide6 is missing, collection fails. Run `make prepare` first.
- No CI/workflow config is present in repo; local `make test` is the authoritative verification path.

## Current tooling reality
- `make lint` is a placeholder message only (no linter configured).
- `.gitignore` still contains legacy Go-oriented patterns; do not infer Go tooling from it.

## Project state from session history
- Main branch already contains the full tray app feature merge (`621603a Merge aws-sso-autologin`).
- Branch-level review closure is recorded in `docs/leyline/plans/2026-05-09-aws-sso-autologin-review-log.md`:
  - `Code review complete - round 4 - 2026-05-09`
  - `Design review complete - round 3 - 2026-05-09`
- The current expected baseline is green locally (`make test`), including tray/UI tests.

## Spec artifacts (source of truth)
- Product spec: `docs/leyline/specs/2026-05-09-aws-sso-autologin-design.md`
- UX spec: `docs/leyline/design/2026-05-09-aws-sso-autologin-ux.md`
- Plan: `docs/leyline/plans/2026-05-09-aws-sso-autologin.md`
- Review log: `docs/leyline/plans/2026-05-09-aws-sso-autologin-review-log.md`

## When changing behavior, update specs in the same task
- If you change runtime behavior, user-visible copy/state semantics, thresholds, failure handling, or contracts, update the matching spec docs first (or in the same change), then code/tests.
- Keep product and UX specs aligned with implementation; do not leave intentional drift undocumented.
- After spec edits, append new approval markers with incremented rounds (same date format already used):
  - Product: `Product spec approved - round <N> - YYYY-MM-DD`
  - UX: `UX spec approved - round <N> - YYYY-MM-DD`
- If review expectations change, record them in the review log and ensure completion markers are re-emitted only after new findings are resolved.

## Minimum verification before claiming done
- Run targeted tests for changed modules plus `make test` before completion claims.
- For tray-host/startup issues, include `make run` output with structured `event=` logs in your notes; those logs are part of the diagnostic contract.
