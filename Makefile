.PHONY: help install run test demo interactive clean ui cli docs venv

# Python binary (use from venv if available)
PYTHON := .venv/bin/python
PIP := .venv/bin/pip

# Default target
help:
	@echo "🎯 STRATEGOS - Available Commands"
	@echo ""
	@echo "  make venv          - Create virtual environment"
	@echo "  make install       - Install dependencies (creates venv if needed)"
	@echo "  make run           - Start API server with web UI"
	@echo "  make test          - Run all tests"
	@echo "  make demo          - Run CLI demo"
	@echo "  make interactive   - Run interactive REPL"
	@echo "  make clean         - Clean generated files"
	@echo "  make ui            - Start server and open UI"
	@echo "  make cli           - Run CLI demo (alias for demo)"
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

# Run tests
test: install
	@$(PYTHON) -m pytest tests/ -v

# Run tests with coverage
test-cov: install
	@$(PYTHON) -m pytest --cov=core tests/

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

# Run with tests first
run-test: install
	@$(PYTHON) strategos.py --test

# Format code (requires black)
format: install
	@$(PYTHON) -m black core/ tests/ *.py

# Lint code (requires ruff)
lint: install
	@$(PYTHON) -m ruff check core/ tests/ *.py
