.PHONY: help venv prepare test test-verbose run run-check run-agent lint clean

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

help:
	@printf "Available targets:\n"
	@printf "  make venv          Create local virtual environment\n"
	@printf "  make prepare       Create venv and install dependencies\n"
	@printf "  make test          Run test suite\n"
	@printf "  make test-verbose  Run test suite with verbose output\n"
	@printf "  make run           Run application module\n"
	@printf "  make lint          Placeholder lint target\n"
	@printf "  make clean         Remove Python/test caches\n"

venv:
	@test -x "$(PYTHON)" || python3 -m venv "$(VENV)"
	@test -x "$(PYTHON)"

prepare: venv
	@"$(PIP)" install --upgrade pip
	@"$(PIP)" install -r requirements.txt

test: venv
	@"$(PYTEST)"

test-verbose: venv
	@"$(PYTEST)" -v

run: venv
	@echo "Running with automatic mode detection (safe in automation contexts)..."
	@"$(PYTHON)" -m aws_sso_autologin --log-level debug

# Add explicit check-only target for scripts that want it explicitly
run-check: venv
	@echo "Running in check-only mode..."
	@"$(PYTHON)" -m aws_sso_autologin --check-only --log-level debug

# Add automation-safe run target with explicit watchdog
run-agent: venv
	@echo "Running in agent-safe mode with watchdog timeout..."
	@AWS_SSO_AUTOLOGIN_WATCHDOG=1 AWS_SSO_AUTOLOGIN_TIMEOUT=60 "$(PYTHON)" -m aws_sso_autologin --check-only --log-level debug

lint: venv
	@printf "No linter configured yet.\n"

clean:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@rm -rf .pytest_cache
