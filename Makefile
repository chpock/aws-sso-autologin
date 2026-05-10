.PHONY: help venv prepare prepare-dev test test-verbose run run-check run-agent lint clean

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest

LOG_LEVEL ?= debug

help:
	@printf "Available targets:\n"
	@printf "  make venv          Create local virtual environment\n"
	@printf "  make prepare       Create venv and install dependencies\n"
	@printf "  make prepare-dev   Create venv and install dev dependencies (includes pytest)\n"
	@printf "  make test          Run test suite\n"
	@printf "  make test-verbose  Run test suite with verbose output\n"
	@printf "  make run           Run application module (LOG_LEVEL=debug by default)\n"
	@printf "  make lint          Placeholder lint target\n"
	@printf "  make clean         Remove Python/test caches\n"
	@printf "\nEnvironment variables:\n"
	@printf "  LOG_LEVEL          Log level: error, warning, info, debug, trace (default: debug)\n"

venv:
	@test -x "$(PYTHON)" || python3 -m venv "$(VENV)"
	@test -x "$(PYTHON)"

prepare: venv
	@"$(PIP)" install --upgrade pip
	@"$(PIP)" install -r requirements.txt

prepare-dev: prepare
	@"$(PIP)" install -e ".[dev]"

test: venv
	@"$(PYTEST)"

test-verbose: venv
	@"$(PYTEST)" -v

run: venv
	@echo "Running with automatic mode detection (safe in automation contexts)..."
	@"$(PYTHON)" -m aws_sso_autologin --log-level $(LOG_LEVEL)

# Add explicit check-only target for scripts that want it explicitly
run-check: venv
	@echo "Running in check-only mode..."
	@"$(PYTHON)" -m aws_sso_autologin --check-only --log-level $(LOG_LEVEL)

# Add automation-safe run target with explicit watchdog
run-agent: venv
	@echo "Running in agent-safe mode with watchdog timeout..."
	@AWS_SSO_AUTOLOGIN_WATCHDOG=1 AWS_SSO_AUTOLOGIN_TIMEOUT=60 "$(PYTHON)" -m aws_sso_autologin --check-only --log-level $(LOG_LEVEL)

lint: venv
	@"$(VENV)/bin/ruff" check .
	@"$(VENV)/bin/ruff" format --check .

clean:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@rm -rf .pytest_cache
