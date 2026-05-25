.PHONY: help install run test demo interactive clean ui cli docs venv deploy deploy-down deploy-logs deploy-shell

# Python binary (use from venv if available)
PYTHON := .venv/bin/python
PIP := .venv/bin/pip

# Default target
help:
	@echo "STRATEGOS - Available Commands"
	@echo ""
	@echo "  make deploy        - Build and start with Docker (production)"
	@echo "  make deploy-down   - Stop Docker containers"
	@echo "  make deploy-logs   - Tail container logs"
	@echo "  make deploy-shell  - Shell into running container"
	@echo ""
	@echo "  make ui            - Start server locally and open browser (dev)"
	@echo "  make install       - Install Python dependencies"
	@echo "  make test          - Run test suite"
	@echo "  make clean         - Remove generated files"
	@echo ""

# Create virtual environment
venv:
	@if command -v pyenv >/dev/null 2>&1; then \
		export PYENV_VERSION=$$(cat .python-version 2>/dev/null || echo "3.12.10"); \
		echo "🐍 Using Python $$(python --version 2>&1)"; \
	fi; \
	if [ ! -d ".venv" ]; then \
		echo "⚠️  Creating virtual environment..."; \
		python -m venv .venv; \
		echo "✓ Virtual environment created"; \
	else \
		echo "✓ Virtual environment already exists"; \
	fi

# Install dependencies
install: venv
	@echo "📦 Installing dependencies..."
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@echo "✓ Dependencies installed"

# Run API server
run: install
	@$(PYTHON) strategos.py --no-browser

# Run with UI in browser
ui: install
	@$(PYTHON) strategos.py

# Run tests (fast — excludes slow integration tests with real-time sleeps)
test: install
	@$(PYTHON) -m pytest tests/ -k "not test_movement" -v

# Run full test suite including slow movement/replay integration tests
test-all: install
	@$(PYTHON) -m pytest tests/ -v

# Run tests with coverage
test-cov: install
	@$(PYTHON) -m pytest --cov=core tests/ -k "not test_movement"

# Run CLI demo
demo: install
	@$(PYTHON) run_simulation.py

cli: demo

# Run interactive mode
interactive: install
	@$(PYTHON) run_simulation.py --interactive

# Clean generated files
clean:
	@echo "🧹 Cleaning generated files..."
	@rm -rf __pycache__ .pytest_cache .coverage
	@rm -rf core/__pycache__ tests/__pycache__
	@rm -f strategos.db strategos_demo.db strategos_interactive.db
	@rm -rf checkpoints/*.pkl
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "✓ Cleanup complete"

# Development mode with auto-reload
dev: install
	@$(PYTHON) -m uvicorn api:app --reload --host 0.0.0.0 --port 8000

# ── Docker deployment ────────────────────────────────────────────────────────

deploy:
	@docker compose up --build -d
	@echo ""
	@echo "Strategos running → http://localhost:$${PORT:-8000}"
	@echo "Logs:  make deploy-logs"
	@echo "Stop:  make deploy-down"

deploy-down:
	docker compose down

deploy-logs:
	docker compose logs -f

deploy-shell:
	docker compose exec strategos /bin/bash

# ── Development ───────────────────────────────────────────────────────────────

# Run with tests first
run-test: install
	@$(PYTHON) strategos.py --test

# Format code (requires black)
format: install
	@$(PYTHON) -m black core/ tests/ *.py

# Lint code (requires ruff)
lint: install
	@$(PYTHON) -m ruff check core/ tests/ *.py
