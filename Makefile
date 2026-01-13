.PHONY: help install install-dev test test-verbose test-coverage clean clean-all lint format type-check run run-experimenter run-optimizer run-geometry-editor docs-check pre-commit-install verify db-populate db-stats db-reset ci all

# Default target - show help
help:
	@echo "Traverso Analyzer - Development Commands"
	@echo ""
	@echo "Installation:"
	@echo "  make install          Install production dependencies"
	@echo "  make install-dev      Install development dependencies"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-verbose     Run tests with verbose output"
	@echo "  make test-coverage    Run tests with coverage report"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Run flake8 linter"
	@echo "  make format           Format code with black"
	@echo "  make format-check     Check formatting without changes"
	@echo "  make type-check       Run mypy type checker"
	@echo "  make docs-check       Validate documentation"
	@echo ""
	@echo "Running Applications:"
	@echo "  make run              Run main GUI application"
	@echo "  make run-experimenter Run flute experimenter"
	@echo "  make run-optimizer    Run flute optimizer"
	@echo "  make run-geometry-editor Run geometry editor"
	@echo ""
	@echo "Database:"
	@echo "  make db-populate      Populate database from JSON files"
	@echo "  make db-stats         Show database statistics"
	@echo "  make db-reset         Reset database (destructive!)"
	@echo ""
	@echo "Verification:"
	@echo "  make verify           Verify installation"
	@echo "  make ci               Run all CI checks locally"
	@echo ""
	@echo "Development:"
	@echo "  make pre-commit-install  Install pre-commit hooks"
	@echo "  make clean            Remove generated files"
	@echo "  make clean-all        Remove all generated files (including DB)"
	@echo "  make all              Run all quality checks"

# Installation targets
install:
	pip install --upgrade pip
	pip install -r requirements.txt

install-dev: install
	pip install pytest pytest-cov black flake8 mypy isort pre-commit

# Testing targets
test:
	pytest

test-verbose:
	pytest -v

test-coverage:
	pytest --cov=. --cov-report=html --cov-report=term
	@echo ""
	@echo "Coverage report generated in htmlcov/index.html"

# Code quality targets
lint:
	@echo "Running flake8..."
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-line-length=100 --statistics

format:
	@echo "Formatting code with black..."
	black .
	@echo "Sorting imports with isort..."
	isort .

format-check:
	@echo "Checking code formatting..."
	black --check .
	@echo "Checking import sorting..."
	isort --check-only .

type-check:
	@echo "Running mypy type checker..."
	mypy . --ignore-missing-imports || true

docs-check:
	@echo "Checking documentation files..."
	@test -f README.md || (echo "❌ README.md missing" && exit 1)
	@test -f ARCHITECTURE.md || (echo "❌ ARCHITECTURE.md missing" && exit 1)
	@test -f CONTRIBUTING.md || (echo "❌ CONTRIBUTING.md missing" && exit 1)
	@test -f INSTALL.md || (echo "❌ INSTALL.md missing" && exit 1)
	@echo "✅ All documentation files present"

# Running applications
run:
	python unified_flute_gui_qt.py

run-experimenter:
	python flute_experimenter.py

run-optimizer:
	python flute_optimizer_gui.py

run-geometry-editor:
	python flute_geometry_editor_qt.py

# Database operations
db-populate:
	python populate_database.py

db-stats:
	python database_statistics.py

db-reset:
	@echo "⚠️  WARNING: This will delete all database data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; echo; \
	if [ "$$REPLY" = "y" ] || [ "$$REPLY" = "Y" ]; then \
		python reset_database.py; \
	else \
		echo "Cancelled."; \
	fi

# Verification
verify:
	@echo "Verifying installation..."
	@python -c "import numpy, scipy, matplotlib, PyQt5; print('✅ Core dependencies OK')" || echo "❌ Missing core dependencies"
	@python -c "import openwind; print('✅ OpenWind OK')" || echo "❌ OpenWind not installed"
	@echo "Running import tests..."
	@pytest tests/test_imports.py -v || echo "❌ Some imports failed"
	@echo "Verification complete!"

# CI simulation
ci: format-check lint type-check test docs-check
	@echo ""
	@echo "✅ All CI checks passed!"

# Deep cleanup
clean-all: clean
	@echo "Removing database and output files..."
	@rm -f *.db *.db-journal *.db-shm *.db-wal 2>/dev/null || true
	@rm -f mi_reporte.txt reporte_flautas.txt 2>/dev/null || true
	@rm -f *.gcode *.nc 2>/dev/null || true
	@echo "✅ Deep cleanup complete"

# Development tools
pre-commit-install:
	pip install pre-commit
	pre-commit install
	@echo "✅ Pre-commit hooks installed"

# Cleanup
clean:
	@echo "Cleaning generated files..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Run all quality checks
all: format-check lint type-check test docs-check
	@echo ""
	@echo "✅ All quality checks passed!"
