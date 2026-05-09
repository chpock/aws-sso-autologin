.PHONY: help venv prepare test test-verbose run lint clean

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
	@"$(PYTHON)" -m aws_sso_autologin --log-level debug

lint: venv
	@printf "No linter configured yet.\n"

clean:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@rm -rf .pytest_cache
