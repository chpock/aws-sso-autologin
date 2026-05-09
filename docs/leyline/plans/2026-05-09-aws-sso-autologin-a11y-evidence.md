# Accessibility Evidence - AWS SSO Autologin

Date: 2026-05-09
Branch: `feat/aws-sso-autologin`

## Automated interaction checks

Command:

```bash
pytest tests/test_tray.py -k "first_row_toggle_contract or paused_switches_first_row or global_error_replaces_toggle or ok_profile_click_closes_menu_no_dialog or error_profile_click_opens_dialog or overflow_uses_40_threshold_and_20_chunks or error_details_dialog_has_required_section_order or default_diagnostics_opens_dialog" -v
```

Observed result:

- `8 passed, 13 deselected in 0.20s`
- Verified first-row control semantics (`Disable/Enable auto-login`, global error action replacement).
- Verified warning/error profile rows open diagnostics and OK rows do not.
- Verified deterministic overflow submenu behavior (`>40` profiles, chunks of `20`).
- Verified diagnostics dialog section order required by UX artifact:
  `Summary -> Incident evidence -> Command -> Exit code -> stderr -> stdout -> Timestamp`.

## Text-label evidence (color independence)

The tray/profile tests validate text-bearing labels for all states (`Syncing`, `Warning`, `Error`, `OK`, `OK (paused)`) and do not rely on icon color alone.

## Keyboard/read-order evidence (headless test harness)

In this CI/headless environment, screen-reader capture is unavailable. Structural evidence is provided through Qt action-trigger tests that verify deterministic action order and dialog content order. Manual screen-reader narration capture should be performed in an interactive Linux desktop session before release.
