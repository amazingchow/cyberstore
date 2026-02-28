# =============================================================================
# GLOBAL VARIABLES
# =============================================================================
.DEFAULT_GOAL := help
SHELL := /bin/bash

PROJECT_NAME := cyberstore
VERSION      := $(shell git describe --tags --always --dirty 2>/dev/null || echo "v0.1.0")
COMMIT_HASH  := $(shell git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_TIME   := $(shell date -u +"%Y-%m-%dT%H:%M:%SZ")
SRC_DIR      := cyberstore
TEST_DIR     := tests
UV           := uv
PYTHON       := $(UV) run python
PYTEST       := $(UV) run pytest
RUFF         := $(UV) run ruff

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
define print_header
	@echo ""
	@echo "═══════════════════════════════════════════════════════════════"
	@echo " $(1)"
	@echo "═══════════════════════════════════════════════════════════════"
endef

# =============================================================================
# TARGETS
# =============================================================================

.PHONY: help
help:  ## Display this help screen
	$(call print_header,cyberstore - Object Storage TUI client (Cloudflare R2 / Aliyun OSS))
	@echo "Version: $(VERSION) ($(COMMIT_HASH))"
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z0-9_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: all
all: clean fmt lint test ## Full build pipeline: clean, format, lint, test

##@ Development

.PHONY: init
init: ## Initialize the project (install dependencies)
	$(call print_header,Installing Dependencies)
	@$(UV) sync --all-extras --dev || $(UV) pip install -e ".[dev]"
	@echo "Environment initialized."

.PHONY: fmt
fmt: ## Format code (ruff format + import sort)
	$(call print_header,Formatting Code)
	@$(RUFF) format .
	@$(RUFF) check --select I --fix .

.PHONY: lint
lint: ## Lint code (read-only check, CI friendly)
	$(call print_header,Running Static Analysis)
	@$(RUFF) format --check .
	@$(RUFF) check .

##@ Testing & execution

.PHONY: test
test: ## Run unit tests with coverage
	$(call print_header,Running Tests)
	@R2_TEST_BUCKET=cyberstore-test-bucket $(PYTEST) -vv --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing $(TEST_DIR) || true

##@ Build & Release

.PHONY: build
build: ## Build standalone binary with PyInstaller (output: dist/cyberstore)
	$(call print_header,Building Standalone Binary)
	@$(UV) pip install pyinstaller --quiet
	@$(UV) run pyinstaller cyberstore.spec --clean --noconfirm
	@echo "Binary built: dist/cyberstore"

.PHONY: dist
dist: ## Build Python sdist + wheel for PyPI
	$(call print_header,Building Python Distribution)
	@$(UV) build
	@echo "Distribution packages:"
	@ls -lh dist/*.whl dist/*.tar.gz 2>/dev/null || true

.PHONY: release-tag
release-tag: ## Create and push a git tag to trigger the release workflow (use: make release-tag VERSION=v1.2.3)
	$(call print_header,Creating Release Tag)
	@test -n "$(VERSION)" || (echo "Usage: make release-tag VERSION=v1.2.3" && exit 1)
	@git tag -a $(VERSION) -m "Release $(VERSION)"
	@git push origin $(VERSION)
	@echo "Tag $(VERSION) pushed — GitHub Actions release workflow triggered."

##@ Build & Clean

.PHONY: clean
clean: ## Clean build artifacts and cache
	$(call print_header,Cleaning up)
	@rm -rf dist build *.egg-info .coverage htmlcov
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type d -name ".ruff_cache" -exec rm -rf {} +
	@find . -type d -name ".mypy_cache" -exec rm -rf {} +
	@find . -type d -name ".coverage" -exec rm -rf {} +
	@find . -type d -name "htmlcov" -exec rm -rf {} +
	@find . -type d -name "build" -exec rm -rf {} +
	@find . -type d -name "dist" -exec rm -rf {} +
