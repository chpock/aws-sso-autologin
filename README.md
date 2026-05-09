# AWS SSO Autologin

A Linux system tray application that monitors AWS SSO sessions and automatically refreshes them before expiration using a serial login queue.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PySide6](https://img.shields.io/badge/PySide6-6.6+-green.svg)](https://pypi.org/project/PySide6/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Automatic Session Refresh**: Monitors AWS SSO sessions every 30 seconds and triggers automatic renewal when sessions reach 50% of their lifetime (30 minutes before expiration)
- **System Tray Integration**: Native Linux system tray icon with real-time status updates, tooltips, and context menu
- **Serial Login Queue**: Ensures login attempts run strictly one at a time to prevent AWS rate limiting and browser conflicts
- **Per-Profile Login Lock**: 8-minute cooldown between login attempts per profile to prevent thrashing
- **Profile Discovery**: Automatically discovers and monitors all SSO-enabled AWS profiles from your AWS config
- **High Cardinality Support**: Supports up to 100 profiles with automatic overflow submenus for easy navigation
- **Memory-Bounded Log Classification**: ROT13-obfuscated pattern corpus for secure log analysis with ~12 MiB total memory budget
- **Tray Host Detection**: Automatically detects and adapts to GNOME, KDE, XFCE, MATE, Cinnamon, and other Linux desktop environments
- **Health Monitoring**: 5-minute heartbeat timeout with automatic session validation
- **Status Window**: Detailed session status window showing all profiles, login times, and queue positions

## Requirements

- Python 3.11 or higher
- Linux desktop environment with system tray support (StatusNotifier or XEmbed)
- AWS CLI v2 installed and configured
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

Once running, the application will appear in your system tray:

- **Left-click**: Show status window with detailed session information
- **Right-click**: Open context menu with profile list and controls
- **Tooltip**: Shows current logged-in profile count (updates every 5 seconds)

### Menu Options

- **Status Window**: Opens the detailed status window showing all profiles
- **Profile List**: Shows all monitored SSO profiles with their current status
  - Profiles with overflow (>25) are grouped into submenus
  - Each profile shows: `Profile: <name> - OK` or `Profile: <name> - Error`
- **Quit**: Gracefully shutdown the application

### Debug Mode

Enable debug logging for troubleshooting:

```bash
AWS_SSO_AUTOLOGIN_DEBUG=1 aws-sso-autologin
```

Or set the environment variable:
```bash
export AWS_SSO_AUTOLOGIN_DEBUG=1
aws-sso-autologin
```

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
- `StatusWindowProxy`: Lazy-initialized detailed status window with profile table
- `ProfileStatus`: Dataclass for per-profile status information
- Features: 25-item menu limit with overflow submenus, 5-second tooltip throttle

### 2. Classifier Module (`classifier.py`)

Memory-bounded log analysis for AWS CLI output:
- `LogClassifier`: Tokenizes and classifies log lines with FIFO eviction
- `LogCategory`: SUCCESS, ERROR_AUTH, ERROR_NETWORK, ERROR_CONFIG, WARNING, INFO, UNKNOWN
- ROT13-obfuscated corpus for privacy protection
- Memory budget: 64 tokens max per sample, 768 samples max (~48 KiB per stream, ~12 MiB total)

### 3. Operator Module (`operator.py`)

Manages session lifecycle and monitoring:
- `HealthOperator`: 30-second monitoring loop, 5-minute heartbeat timeout
- `SessionOperator`: Tracks sessions and triggers renewal at 50% threshold
- `LoginOperator`: Serial login queue with 8-minute per-profile lock
- Thread-safe queue processing with proper locking

### 4. Service Module (`service.py`)

Tray host abstraction and environment detection:
- `TrayHost`: Abstract interface for tray host operations
- `ConcreteTrayHost`: Implementation for detected desktop environment
- `detect_tray_host()`: Detects GNOME, KDE, XFCE, MATE, Cinnamon, Pantheon, Budgie, LXQt
- `check_tray_host_available()`: Preflight validation before startup

### Supporting Modules

- **`aws.py`**: AWS CLI integration for session checking (`sts get-caller-identity`), SSO login, and profile discovery
- **`models.py`**: Domain models including `ProfileConfig` and `SessionInfo`
- **`checker.py`**: Session checking logic
- **`cli.py`**: CLI command execution wrapper
- **`logger.py`**: Structured logging with debug mode support
- **`constants.py`**: Application constants and configuration values
- **`errors.py`**: Custom exception hierarchy

## Configuration

### AWS Configuration

Ensure your AWS config file (`~/.aws/config`) contains SSO profiles:

```ini
[profile my-sso-profile]
sso_start_url = https://my-org.awsapps.com/start
sso_region = us-east-1
sso_account_id = 123456789012
sso_role_name = AdministratorAccess
```

### Application Configuration

The application reads configuration from:
- Preferred: `$XDG_CONFIG_HOME/aws-sso-autologin/config.yaml`
- Fallback: `~/.config/aws-sso-autologin/config.yaml`

Example configuration:

```yaml
config_version: 1
safe_mode: false
profiles:
  my-sso-profile:
    browser:
      - google-chrome
      - --profile-directory=Work
      - --new-window
```

#### Configuration Options

- `config_version`: Configuration schema version (current: 1)
- `safe_mode`: Start with monitoring disabled (default: false)
- `profiles`: Per-profile browser overrides (optional)

### Environment Variables

- `AWS_SSO_AUTOLOGIN_DEBUG`: Enable debug logging (set to `1`)
- `AWS_SSO_AUTOLOGIN_SAFE_MODE`: Start in safe mode with monitoring disabled (set to `1`)
- `DESKTOP_SESSION` / `XDG_CURRENT_DESKTOP`: Used for tray host detection

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
4. Review error details in the status window
5. Ensure 8-minute login lock has expired between attempts

### Debug Logging

Enable debug mode to see detailed logs:

```bash
AWS_SSO_AUTOLOGIN_DEBUG=1 aws-sso-autologin 2>&1 | tee autologin.log
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
