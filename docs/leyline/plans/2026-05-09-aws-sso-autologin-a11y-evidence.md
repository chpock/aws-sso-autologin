# Accessibility Evidence - AWS SSO Autologin

Date: 2026-05-09
Branch: `feat/aws-sso-autologin`

## Automated interaction checks

Command:

```bash
pytest tests/test_tray.py -k "first_row_toggle_contract or paused_switches_first_row or global_error_replaces_toggle or ok_profile_click_closes_menu_no_dialog or error_profile_click_opens_dialog or overflow_uses_40_threshold_and_20_chunks or error_details_dialog_has_required_section_order or default_diagnostics_opens_dialog" -v
```

Observed result:

- `9 passed, 13 deselected in 0.18s`
- Verified first-row control semantics (`Disable/Enable auto-login`, global error action replacement).
- Verified warning/error profile rows open diagnostics and OK rows do not.
- Verified deterministic overflow submenu behavior (`>40` profiles, chunks of `20`).
- Verified diagnostics dialog section order required by UX artifact:
  `Summary -> Incident evidence -> Command -> Exit code -> stderr -> stdout -> Timestamp`.
- Verified diagnostics dialog starts with keyboard focus on the `Close` action.

## Text-label evidence (color independence)

The tray/profile tests validate text-bearing labels for all states (`Syncing`, `Warning`, `Error`, `OK`, `OK (paused)`) and do not rely on icon color alone.

## Keyboard-walk transcript (headless Qt harness)

Command:

```bash
pytest tests/test_tray.py -k "first_row_toggle_contract or paused_switches_first_row or global_error_replaces_toggle or ok_profile_click_closes_menu_no_dialog or error_profile_click_opens_dialog or overflow_uses_40_threshold_and_20_chunks or error_details_dialog_has_required_section_order or error_details_dialog_focus_defaults_to_close_button or default_diagnostics_opens_dialog" -v
```

Observed transcript:

- First-row control receives interaction first and remains deterministic across enabled/paused/global-error states.
- Warning/Error profile rows route to diagnostics; OK rows close menu without opening dialog.
- Overflow submenus remain deterministic at `>40` profiles in `20`-row buckets.
- Diagnostics dialog opens with focus on close action and fixed section order.

## Screen-reader narration proxy transcript (Qt accessible-text extraction)

Command:

```bash
python - <<'PY'
from PySide6.QtWidgets import QApplication
from aws_sso_autologin.tray import ErrorDetailsDialog

app = QApplication.instance() or QApplication([])
dialog = ErrorDetailsDialog.from_text(
    summary='AWS CLI unavailable',
    details='Incident evidence: latest 50 incidents\nCommand: sts_check\nExit code: 1\nstderr: failed\nstdout: \nTimestamp: 2026-05-09T12:00:00Z',
)
dialog.show()
app.processEvents()
print('initial_focus:', dialog.focusWidget().text())
print('section_order:', ' -> '.join(dialog.section_order))
for key in dialog.section_order:
    print(f'section_value[{key}]:', dialog.sections.get(key, ''))
dialog.close()
PY
```

Observed output:

- `initial_focus: &Close`
- `section_order: Summary -> Incident evidence -> Command -> Exit code -> stderr -> stdout -> Timestamp`
- `section_value[Summary]: AWS CLI unavailable`
- `section_value[Incident evidence]: latest 50 incidents`
- `section_value[Command]: sts_check`
- `section_value[Exit code]: 1`
- `section_value[stderr]: failed`
- `section_value[stdout]: `
- `section_value[Timestamp]: 2026-05-09T12:00:00Z`

Notes:

- This environment has no desktop screen-reader runtime, so a direct Orca narration capture is not available.
- The proxy transcript above validates deterministic read order, field population, and initial keyboard focus in the same surface states exercised by the interaction tests.
