# Agent Python Project developer entrypoints.
SHELL := /bin/bash
PROJECT_ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
VENV := $(PROJECT_ROOT)/.venv
PY := $(VENV)/bin/python
PYTHON_VERSION ?= 3.12
DATA_DIR ?= .data
DATA_ROOT := $(if $(filter /%,$(DATA_DIR)),$(DATA_DIR),$(PROJECT_ROOT)/$(DATA_DIR))
PYTEST_CACHE := -o cache_dir=$(DATA_ROOT)/cache/pytest

export RUFF_CACHE_DIR := $(DATA_ROOT)/cache/ruff
export MYPY_CACHE_DIR := $(DATA_ROOT)/cache/mypy

.DEFAULT_GOAL := help

.PHONY: help bootstrap venv lock run doctor format format-check lint typecheck test coverage \
	complexity-gate shell-lint-gate lint-md lint-doc-links lint-spec-plan plan-status \
	ci-checks ci ci-github build quality code-quality quality-report

help: ## List available targets
	@awk 'BEGIN {FS = ":.*## "; print "Usage: make <target>\n"} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap: ## Create/update .venv from uv.lock with development tools
	@command -v uv >/dev/null 2>&1 || { echo "ERROR: uv is required"; exit 1; }
	@source "$(PROJECT_ROOT)/scripts/shared/common.sh"; apy_load_env; \
		uv sync --locked --extra dev --python "$(PYTHON_VERSION)"

venv: bootstrap ## Alias for bootstrap

lock: ## Refresh uv.lock after dependency changes
	@source "$(PROJECT_ROOT)/scripts/shared/common.sh"; apy_load_env; uv lock

run: ## Run the starter project identity command
	@test -x "$(VENV)/bin/agent-py" || { echo "ERROR: run 'make bootstrap' first"; exit 1; }
	@"$(VENV)/bin/agent-py" info

doctor: ## Verify required tools, files, and the installed package
	@command -v git >/dev/null
	@command -v uv >/dev/null
	@command -v make >/dev/null
	@test -f pyproject.toml -a -f uv.lock -a -f AGENTS.md
	@test -x "$(PY)" || { echo "ERROR: run 'make bootstrap' first"; exit 1; }
	@"$(PY)" -c 'import agent_py; print(agent_py.project_info().distribution)'

format: ## Format production code and tests with Ruff
	@"$(VENV)/bin/ruff" format src tests
	@"$(VENV)/bin/ruff" check --fix src tests

format-check: ## Check Python formatting without changing files
	@"$(VENV)/bin/ruff" format --check src tests

lint: ## Run Ruff lint checks
	@"$(VENV)/bin/ruff" check src tests

typecheck: ## Run mypy over production code
	@"$(VENV)/bin/mypy" --python-version "$(PYTHON_VERSION)"

test: ## Run deterministic unit tests
	@"$(PY)" -m pytest $(PYTEST_CACHE)

coverage: ## Run tests and enforce the coverage floor
	@"$(PY)" -m pytest $(PYTEST_CACHE) --cov=agent_py --cov-report=term-missing

complexity-gate: ## Fail on Radon D-or-worse or cognitive complexity above 15
	@output="$$($(VENV)/bin/radon cc src tests -s -n D)"; \
		if [ -n "$$output" ]; then printf '%s\n' "$$output"; exit 1; fi
	@mkdir -p "$(DATA_ROOT)/cache/complexipy"
	@cd "$(DATA_ROOT)/cache/complexipy"; \
		output="$$($(VENV)/bin/complexipy "$(PROJECT_ROOT)/src" "$(PROJECT_ROOT)/tests" \
		--max-complexity-allowed 15 --failed --ignore-complexity --color no --plain --sort desc)"; \
		if [ -n "$$output" ]; then printf '%s\n' "$$output"; exit 1; fi

shell-lint-gate: ## Check every tracked shell script with bash and ShellCheck
	@find scripts -type f -name '*.sh' -print0 | xargs -0 -r -n1 bash -n
	@find scripts -type f -name '*.sh' -print0 | \
		xargs -0 -r "$(VENV)/bin/shellcheck" -x -P SCRIPTDIR -S warning

lint-md: ## Lint repository Markdown and then validate relative links
	@"$(PY)" -m pymarkdown scan -r README.md AGENTS.md CLAUDE.md GEMINI.md docs
	@$(MAKE) --no-print-directory lint-doc-links

lint-doc-links: ## Check that relative Markdown links and anchors resolve
	@"$(PY)" -m agent_py.quality.doc_links --root "$(PROJECT_ROOT)"

lint-spec-plan: ## Check capability registry, task structure, status, and ordering
	@"$(PY)" -m agent_py.quality.plan_integrity --root "$(PROJECT_ROOT)"

plan-status: ## Count tasks by lane/status and show the next eligible work
	@"$(VENV)/bin/agent-py-plan" --root "$(PROJECT_ROOT)"

ci-checks: format-check lint typecheck complexity-gate shell-lint-gate lint-doc-links lint-spec-plan

ci: ci-checks test ## Run the required local and GitHub CI gate

ci-github: ci ## Explicit GitHub Actions entrypoint

build: ## Build source and wheel distributions
	@source "$(PROJECT_ROOT)/scripts/shared/common.sh"; apy_load_env; uv build

quality: ci-checks coverage lint-md build ## Run the full local quality suite

code-quality: quality ## Alias for the full local quality suite

quality-report: ## Report Python/shell files over the 250-line soft limit
	@find src tests scripts -type f \( -name '*.py' -o -name '*.sh' \) -print0 | \
		xargs -0 -r wc -l | awk '$$2 != "total" && $$1 > 250 {print}' | sort -nr
