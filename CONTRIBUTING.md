# Contributing to Traverso Analyzer

Thank you for your interest in contributing to Traverso Analyzer! This document provides guidelines and best practices for contributing to the project.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Code Style](#code-style)
4. [Testing](#testing)
5. [Commit Guidelines](#commit-guidelines)
6. [Pull Request Process](#pull-request-process)
7. [Project Structure](#project-structure)
8. [Development Workflow](#development-workflow)

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Git
- Basic understanding of acoustic modeling and/or baroque flutes (helpful but not required)

### Reporting Issues

Before creating an issue:
1. Check existing issues to avoid duplicates
2. Use the issue template (if available)
3. Provide detailed information:
   - Python version
   - Operating system
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant error messages/logs

### Suggesting Features

When suggesting new features:
1. Clearly describe the use case
2. Explain the expected behavior
3. Consider backward compatibility
4. Discuss potential implementation approaches

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/analyze-traverso-v2.git
cd analyze-traverso-v2
```

### 2. Create a Virtual Environment

```bash
# Using venv (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda
conda create -n traverso python=3.10
conda activate traverso
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note**: OpenWind may require special installation. If not available via pip:
```bash
# Clone and install from source
git clone https://gitlab.inria.fr/openwind/openwind.git
cd openwind
pip install -e .
```

### 4. Install Development Dependencies

```bash
pip install pytest pytest-cov black flake8 mypy
```

### 5. Verify Installation

```bash
# Run the main GUI to verify setup
python unified_flute_gui_qt.py
```

## Code Style

### Python Style Guide

This project follows [PEP 8](https://www.python.org/dev/peps/pep-0008/) with some modifications.

#### General Guidelines

1. **Line Length**: Maximum 100 characters (not strict 79)
2. **Indentation**: 4 spaces (no tabs)
3. **Quotes**: Prefer double quotes `"` for strings, single quotes `'` for dict keys when appropriate
4. **Imports**: Group in order (stdlib, third-party, local)

```python
# Good
import os
import sys

import numpy as np
from matplotlib import pyplot as plt

from flute_data import FluteData
from constants import FLUTE_PARTS_ORDER
```

5. **Type Hints**: Use type hints for function signatures (gradually being adopted)

```python
def calculate_inharmonicity(
    flute_data: FluteData,
    note: str
) -> float:
    """Calculate inharmonicity for a given note."""
    pass
```

6. **Docstrings**: Use Google-style docstrings

```python
def complex_function(param1: str, param2: int) -> Dict[str, Any]:
    """
    Brief description of what the function does.

    More detailed explanation if needed. Can span multiple lines
    and include references to papers or documentation.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Dictionary containing results with keys:
            - 'value': The calculated value
            - 'metadata': Additional information

    Raises:
        ValueError: If param2 is negative
        FileNotFoundError: If required file not found

    Example:
        >>> result = complex_function("test", 42)
        >>> print(result['value'])
        42
    """
    pass
```

#### Language Conventions

**⚠️ Important**: We are transitioning to English-only codebase.

- **Code**: Write in English (variables, functions, classes, comments)
- **Documentation**: English for READMEs, docstrings, and technical docs
- **User-facing content**: Can be in Spanish or bilingual if primary users are Spanish-speaking

```python
# ✅ Good
def calculate_speed_of_sound(temp_celsius: float) -> float:
    """Calculate speed of sound in air at given temperature."""
    pass

# ❌ Avoid (legacy code may have this)
def calcular_velocidad_sonido(temp_celsius: float) -> float:
    """Calcula la velocidad del sonido..."""
    pass
```

### Code Formatting

Use `black` for automatic formatting:

```bash
# Format a file
black path/to/file.py

# Format entire project
black .

# Check without modifying
black --check .
```

### Linting

Use `flake8` for linting:

```bash
# Lint entire project
flake8 .

# Lint specific file
flake8 path/to/file.py
```

Configuration in `setup.cfg` or `.flake8`:
```ini
[flake8]
max-line-length = 100
exclude = .git,__pycache__,backup_*,venv
ignore = E203,W503
```

## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_flute_data.py

# Run specific test
pytest tests/test_flute_data.py::test_load_from_json
```

### Writing Tests

**⚠️ Note**: Test infrastructure is being built. Early tests should focus on:
1. Data model integrity
2. Acoustic calculation regression tests
3. Database operations

#### Test Structure

```python
# tests/test_flute_data.py
import pytest
from pathlib import Path
from flute_data import FluteData

class TestFluteData:
    """Tests for FluteData class."""

    @pytest.fixture
    def sample_json_path(self, tmp_path):
        """Create a sample JSON file for testing."""
        json_content = {
            "flute_model": "Test_Flute",
            "headjoint": {
                "measurements": [{"position": 0, "diameter": 10}]
            }
            # ... minimal valid structure
        }
        json_file = tmp_path / "test_flute.json"
        json_file.write_text(json.dumps(json_content))
        return json_file

    def test_load_from_json(self, sample_json_path):
        """Test loading flute from JSON file."""
        flute = FluteData(str(sample_json_path))
        assert flute.flute_model == "Test_Flute"
        assert "headjoint" in flute.data

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises appropriate error."""
        with pytest.raises(FileNotFoundError):
            FluteData("/nonexistent/path.json")
```

#### Test Coverage Goals

- **Core modules**: >80% coverage (flute_data, analysis_module, flute_operations)
- **GUI modules**: >50% coverage (focus on business logic)
- **Utility modules**: >70% coverage

## Commit Guidelines

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

#### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks, dependency updates

#### Examples

```
feat(analysis): add Q-factor calculation to acoustic analysis

Implement Q-factor metric to assess resonance peak sharpness.
This metric helps evaluate the "speaking quality" of flutes.

Closes #42
```

```
fix(database): prevent duplicate entries when reimporting flutes

Previously, reimporting a flute would create duplicate records.
Now checks for existing entries by flute_model name.

Fixes #67
```

```
refactor(gui): extract plot update logic to separate module

Split large unified_flute_gui_qt.py by moving plot update
methods to new plot_updater.py module. No functional changes.
```

### Branch Naming

- `feature/description`: New features
- `fix/description`: Bug fixes
- `refactor/description`: Code refactoring
- `docs/description`: Documentation updates

Examples:
- `feature/add-tonal-balance-metric`
- `fix/database-connection-leak`
- `refactor/split-flute-operations`

## Pull Request Process

### Before Submitting

1. **Update from main branch**:
   ```bash
   git checkout main
   git pull origin main
   git checkout your-branch
   git rebase main
   ```

2. **Run tests**:
   ```bash
   pytest
   ```

3. **Run linter**:
   ```bash
   flake8 .
   black --check .
   ```

4. **Update documentation** if needed

### PR Template

When creating a PR, include:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Refactoring
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] Manual testing performed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented if necessary)

## Related Issues
Closes #XX
```

### Review Process

1. At least one approving review required
2. All CI checks must pass
3. No merge conflicts
4. Branch up-to-date with main

## Project Structure

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

### Adding New Modules

When creating new modules:

1. **Placement**: Consider logical grouping
   - Core data models → root directory
   - GUI components → consider `gui/` subdirectory (future)
   - Utilities → root directory with clear naming

2. **Naming**: Use descriptive, unambiguous names
   - ✅ `sensitivity_analysis.py`
   - ❌ `analysis.py` (too generic)

3. **Structure**: Follow existing patterns
   ```python
   """
   Module description.

   Longer explanation if needed.
   """

   import logging
   from typing import List, Dict, Any

   from constants import CONSTANT_NAME
   from flute_data import FluteData

   logger = logging.getLogger(__name__)


   class MyNewClass:
       """Class docstring."""

       def __init__(self):
           """Initialize."""
           pass
   ```

4. **Documentation**: Add to ARCHITECTURE.md

## Development Workflow

### Typical Feature Development

1. **Create issue** describing the feature
2. **Create branch** from main: `feature/my-feature`
3. **Implement** with tests
4. **Test locally**:
   ```bash
   pytest
   flake8 .
   python unified_flute_gui_qt.py  # Manual testing
   ```
5. **Commit** with conventional commit messages
6. **Push** and create PR
7. **Address review** feedback
8. **Merge** after approval

### Working with Large Refactorings

For large changes (e.g., splitting big files):

1. **Create tracking issue** with checklist
2. **Make incremental PRs**:
   - PR 1: Extract utilities
   - PR 2: Extract plotting functions
   - PR 3: Final cleanup
3. **Ensure backward compatibility** between PRs
4. **Keep main branch stable** at all times

### Database Migrations

When changing database schema:

1. **Never modify** `db_schema.py` directly for existing databases
2. **Create migration script**: `migrations/migration_YYYYMMDD_description.py`
3. **Test migration** on copy of production database
4. **Document** in migration script and CHANGELOG

## Questions or Help

- **General questions**: Open a discussion on GitHub
- **Bug reports**: Create an issue
- **Feature ideas**: Create an issue with "enhancement" label
- **Urgent matters**: Contact maintainers directly

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

---

**Thank you for contributing to Traverso Analyzer!** 🎵
