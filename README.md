# AWS SSO Autologin

A Linux system tray application that monitors AWS SSO sessions and automatically refreshes them before expiration using a serial login queue.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PySide6](https://img.shields.io/badge/PySide6-6.6+-green.svg)](https://pypi.org/project/PySide6/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Automatic Session Refresh**: Monitors AWS SSO sessions every 30 seconds and queues login only on explicit expired/invalid session detection
- **System Tray Integration**: Native Linux system tray icon with real-time status updates, tooltips, and a deterministic context menu contract
- **Serial Login Queue**: Ensures login attempts run strictly one at a time to prevent AWS rate limiting and browser conflicts
- **Per-Profile Login Lock**: 5-minute cooldown between login attempts per profile to prevent thrashing
- **Profile Discovery**: Automatically discovers and monitors all SSO-enabled AWS profiles from your AWS config
- **Persistent Global Pause**: Preserve the top-level monitoring enabled/paused state across restarts, with global pause taking precedence over all profile states
- **Persistent Per-Profile Pause**: Pause or resume individual OK profiles from the tray menu, with state preserved across restarts
- **High Cardinality Support**: Supports up to 100 profiles with deterministic overflow submenus when tracked profiles exceed 40 (chunks of 20)
- **Memory-Bounded Log Classification**: ROT13-obfuscated pattern corpus for secure log analysis with 48 KiB per stream budget
- **Tray Host Detection**: Automatically detects and adapts to GNOME, KDE, XFCE, MATE, Cinnamon, and other Linux desktop environments
- **Health Monitoring**: 5-minute heartbeat timeout with automatic session validation
- **Diagnostics Dialog**: Warning/error rows open structured diagnostics with summary, command context, streams, and timestamp

## Requirements

- Python 3.11 or higher
- Linux desktop environment with system tray support (StatusNotifier or XEmbed)
- AWS CLI v2.9.0 or higher installed and configured
- PySide6 6.6.0 or higher

## Installation

### From Source

1. Clone the repository:
```bash
git clone <repository-url>
cd aws-sso-autologin
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate
```

3. Install the package:
```bash
pip install -e .
```

Or install from requirements:
```bash
pip install -r requirements.txt
```

### Development Installation

For development with test dependencies:
```bash
pip install -e ".[dev]"
```

## Usage

### Basic Usage

Start the application from the command line:

```bash
aws-sso-autologin
```

Or run as a Python module:

```bash
python -m aws_sso_autologin
```

### System Tray Interface

Once running, the application appears in your system tray:

- **Right-click**: Open context menu with global control row, profile rows, and quit action
- **First row**: `Pause Monitoring` / `Resume Monitoring`, or `Show startup/sync error` for blocking global failures
- **Tooltip**: Shows `Profiles OK: <count>/<total>` and current icon semantic state

### Menu Options

- **Global control row**: Toggle monitoring or open blocking startup/sync diagnostics
- **Profile list**: Shows current profile state and the next action together in the row label
  - Example active row: `dev - OK -> Pause monitoring`
  - Example paused row: `dev - OK (paused) -> Resume monitoring`
  - After resuming an individually paused profile, the row becomes `dev - Syncing...` until a fresh status check completes
  - Example diagnostics row: `dev - Error -> Show details`
  - While global monitoring is paused, rows with no per-profile action show explicit global-pause copy and are visually disabled
  - Profiles overflow into deterministic submenus when count exceeds 40
  - Overflow bucket size is 20 profiles per submenu
- **Quit**: Gracefully shutdown the application

### CLI Runtime Options

Show help and available options:

```bash
aws-sso-autologin --help
```

Show app version and exit:

```bash
aws-sso-autologin --version
aws-sso-autologin -V
```

Run startup preflight checks only (without starting the tray UI):

```bash
aws-sso-autologin --check-only
```

Set log verbosity:

```bash
aws-sso-autologin --log-level debug
aws-sso-autologin --log-level trace
```

Set log output format:

```bash
aws-sso-autologin --log-format text
aws-sso-autologin --log-format json
```

Text logging is colorized on TTY and plain on non-TTY.

### Safe Mode

Start with monitoring disabled (for rollback scenarios):

```bash
AWS_SSO_AUTOLOGIN_SAFE_MODE=1 aws-sso-autologin
```

## Architecture

The application follows a modular architecture with four main components:

### 1. Tray Module (`tray.py`)

Manages the system tray UI and user interaction:
- `StatusTray`: Main tray icon with menu, tooltip management, and icon state
- `ErrorDetailsDialog`: Structured diagnostics surface for warning/error states
- `ProfileStatus`: Dataclass for per-profile status information
- Features: first-row global control semantics, profile interaction routing, deterministic overflow submenus, 5-second tooltip throttle

### 2. Classifier Module (`classifier.py`)

Memory-bounded log analysis for AWS CLI output:
- `LogClassifier`: Tokenizes and classifies log lines with FIFO eviction
- `LogCategory`: SUCCESS, ERROR_AUTH, ERROR_NETWORK, ERROR_CONFIG, WARNING, INFO, UNKNOWN
- ROT13-obfuscated corpus for privacy protection
- Memory budget: 64 tokens max per sample, 768 samples max (48 KiB per stream, 0.140625 MiB total across three streams)

### 3. Operator Module (`operator.py`)

Manages session lifecycle and monitoring:
- `HealthOperator`: 30-second monitoring loop, 5-minute heartbeat timeout
- `SessionOperator`: Queues login only when checker classifies explicit expired/invalid SSO session failures
- `LoginOperator`: Serial login queue with 5-minute per-profile lock
- Thread-safe queue processing with proper locking

### 4. Service Module (`service.py`)

Tray host abstraction and environment detection:
- `TrayHost`: Abstract interface for tray host operations
- `ConcreteTrayHost`: Implementation for detected desktop environment
- `detect_tray_host()`: Detects GNOME, KDE, XFCE, MATE, Cinnamon, Pantheon, Budgie, LXQt
- `check_tray_host_available()`: Preflight validation before startup

### Supporting Modules

- **`aws.py`**: AWS CLI integration for session checking (`sts get-caller-identity`), SSO login, and profile discovery
- **`aws.py`**: Includes secure temporary browser-wrapper lifecycle for per-profile `aws sso login` overrides
- **`models.py`**: Domain models including `ProfileConfig` and `SessionInfo`
- **`checker.py`**: Session checking logic
- **`cli.py`**: CLI command execution wrapper
- **`logger.py`**: Structured logging with debug mode support
- **`constants.py`**: Application constants and configuration values
- **`errors.py`**: Custom exception hierarchy

## Configuration

### AWS Configuration

Ensure your AWS config file (`~/.aws/config`) contains SSO profiles in the
modern `sso-session` format:

```ini
[profile my-sso-profile]
sso_session = my-sso
sso_account_id = 123456789012
sso_role_name = AdministratorAccess

[sso-session my-sso]
sso_start_url = https://my-org.awsapps.com/start
sso_region = us-east-1
sso_registration_scopes = sso:account:access
```

This project detects SSO profiles by checking `sso_session` on each profile and
does not support legacy inline SSO profile format.

The modern `sso-session` profile format was added to AWS CLI in v2.9.0.

### Application Configuration

The application reads configuration from:
- Preferred: `$XDG_CONFIG_HOME/aws-sso-autologin/config.yaml`
- Fallback: `~/.config/aws-sso-autologin/config.yaml`

Example configuration:

```yaml
config_version: 1
safe_mode: false
logging:
  level: info
  format: text
profiles:
  my-sso-profile:
    browser:
      - /usr/bin/chromium
      - --profile-directory=Profile 1
  another-profile:
    browser:
      - google-chrome
      - --profile-directory=Work
      - --new-window
```

#### Configuration Options

- `config_version`: Configuration schema version (current: 1)
- `safe_mode`: Start with monitoring disabled (default: false)
- `logging.level`: Log level (`error`, `warning`, `info`, `debug`, `trace`)
- `logging.format`: Log format (`text`, `json`)
- `profiles`: Per-profile browser overrides (optional)

### Environment Variables

- `AWS_SSO_AUTOLOGIN_LOG_LEVEL`: Log level override (`error|warning|info|debug|trace`)
- `AWS_SSO_AUTOLOGIN_LOG_FORMAT`: Log format override (`text|json`)
- `AWS_SSO_AUTOLOGIN_SAFE_MODE`: Start in safe mode with monitoring disabled (set to `1`)
- `AWS_SSO_AUTOLOGIN_TRAY_LOSS_BEHAVIOR`: Tray host loss behavior (`pause|continue`)
- `DESKTOP_SESSION` / `XDG_CURRENT_DESKTOP`: Used for tray host detection

### State File

Global and per-profile paused/running state are persisted in a JSON state file:

- Preferred path: `$XDG_STATE_HOME/aws-sso-autologin/state.json`
- Fallback path: `~/.local/state/aws-sso-autologin/state.json`
- Schema: versioned JSON with a top-level `global` section plus profile entries under `profiles`, designed for future state values
- Permissions: state directory `0700`, state file `0600`
- Safety: symlinked state-path components are ignored on read, refused on write, and normal writes are atomic

When global monitoring is paused, it takes precedence over all per-profile states until resumed. Safe mode is still a runtime-only override for that run. Tests use in-memory or temporary state, so your normal state file does not affect test runs.

## Troubleshooting

### Tray Icon Not Visible

**Problem**: The application starts but no tray icon appears.

**Solutions**:
1. Ensure your desktop environment supports system tray (StatusNotifier or XEmbed)
2. Check if a compatible tray host is detected: GNOME, KDE, XFCE, MATE, Cinnamon, etc.
3. Some desktop environments may require a system tray extension (e.g., GNOME Shell requires a tray extension)
4. Check stdout for tray host detection messages

### AWS CLI Not Found

**Problem**: Error message "AWS CLI not found" on startup.

**Solutions**:
1. Ensure AWS CLI v2 is installed: `aws --version`
2. Verify `aws` is in your PATH: `which aws`
3. Install AWS CLI v2 following [AWS documentation](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html)

### No SSO Profiles Detected

**Problem**: "No SSO profiles found" message.

**Solutions**:
1. Verify your AWS config file exists: `cat ~/.aws/config`
2. Ensure profiles have `sso_start_url` configured
3. Check that profiles are valid: `aws configure list-profiles`
4. Verify the profile is SSO-enabled: `aws configure get sso_start_url --profile <profile-name>`

### Login Failures

**Problem**: SSO login attempts fail repeatedly.

**Solutions**:
1. Check AWS CLI credentials: `aws sts get-caller-identity --profile <profile-name>`
2. Verify SSO start URL is accessible in your browser
3. Check for network connectivity issues
4. Review error details from the diagnostics dialog opened by warning/error profile rows
5. Ensure 5-minute login lock has expired between attempts

### Debug Logging

Enable verbose logs to troubleshoot startup/session issues:

```bash
aws-sso-autologin --log-level debug 2>&1 | tee autologin.log
```

### Testing

Run the test suite to verify installation:

```bash
python -m pytest tests/ -v
```

### Known Limitations

- **Non-English locales**: The classifier assumes English AWS CLI error output. Set `LANG=C` if using non-English locales.
- **NFS/network filesystems**: File watchers may behave unpredictably on NFS-mounted directories.
- **X11/XEmbed**: Modern StatusNotifier-compatible trays are required; older XEmbed-only environments may not work.
- **Queue visibility**: At 50+ profiles, queue position is not visible (will be added in v2).

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please ensure:
- Code follows the existing style
- Tests pass: `python -m pytest`
- New features include tests
- Documentation is updated

## Support

For issues and feature requests, please use the project issue tracker.
