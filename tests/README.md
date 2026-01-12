# Tests for Traverso Analyzer

This directory contains the test suite for the Traverso Analyzer project.

## Structure

```
tests/
├── __init__.py              # Package initialization
├── conftest.py              # Shared pytest fixtures
├── README.md                # This file
├── test_imports.py          # Import verification tests
├── test_constants.py        # Constants module tests
└── [future test files]      # Additional test modules
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_constants.py
```

### Run specific test class
```bash
pytest tests/test_imports.py::TestCoreImports
```

### Run specific test function
```bash
pytest tests/test_constants.py::TestSpeedOfSound::test_speed_at_20_celsius
```

### Run with coverage
```bash
pytest --cov=. --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`

### Run tests and show print statements
```bash
pytest -s
```

## Test Categories

### Import Tests (`test_imports.py`)
- Verify that all core modules can be imported
- Check for syntax errors and missing dependencies
- Quick smoke test for basic functionality

### Constants Tests (`test_constants.py`)
- Verify constant values are correct
- Test utility functions (e.g., speed of sound calculation)
- Ensure conversion factors are accurate

### Future Test Modules

#### Planned Test Files
- `test_flute_data.py`: Tests for FluteData class
  - Loading from JSON
  - Saving to JSON
  - Data validation
  - Acoustic analysis integration

- `test_flute_operations.py`: Tests for FluteOperations
  - Geometry calculations
  - Plotting functions
  - Analysis methods

- `test_analysis_module.py`: Tests for FluteAnalyzer
  - Inharmonicity calculation
  - MOC calculation
  - B_I/ESPE calculation
  - Export functions

- `test_db_operations.py`: Tests for database operations
  - Schema creation
  - CRUD operations
  - Cache functionality

- `test_sensitivity_analysis.py`: Tests for sensitivity analysis
  - Parameter variation
  - Variant generation
  - Result analysis

## Writing New Tests

### Test Naming Convention
- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>` or `Test<Functionality>`
- Test functions: `test_<what_is_being_tested>`

### Example Test Structure

```python
"""
Brief description of what this test module covers.
"""

import pytest
from module_to_test import ClassToTest


class TestClassToTest:
    """Tests for ClassToTest."""

    @pytest.fixture
    def sample_instance(self):
        """Fixture providing a sample instance."""
        return ClassToTest(param="value")

    def test_basic_functionality(self, sample_instance):
        """Test that basic function works correctly."""
        result = sample_instance.some_method()
        assert result == expected_value

    def test_error_handling(self):
        """Test that errors are raised appropriately."""
        with pytest.raises(ValueError):
            ClassToTest(invalid_param=True)
```

### Using Fixtures

Fixtures are defined in `conftest.py` and are available to all tests:

```python
def test_with_temp_file(temp_flute_json_file):
    """Use the temp_flute_json_file fixture."""
    # temp_flute_json_file is a Path to a temporary JSON file
    assert temp_flute_json_file.exists()
```

## Test Coverage Goals

| Module Category | Target Coverage |
|----------------|-----------------|
| Core Data Models | >80% |
| Business Logic | >80% |
| Database Operations | >70% |
| GUI (business logic only) | >50% |
| Utilities | >70% |

## Continuous Integration

Tests are automatically run on every push via GitHub Actions (if configured).

## Testing Guidelines

1. **Isolation**: Each test should be independent
2. **Clarity**: Test names should clearly describe what is being tested
3. **Coverage**: Aim for both happy path and error cases
4. **Performance**: Keep tests fast (avoid expensive acoustic calculations when possible)
5. **Fixtures**: Use fixtures for common setup to avoid duplication

## Skipping Tests

Skip tests that require external dependencies not available in CI:

```python
@pytest.mark.skip(reason="Requires OpenWind installation")
def test_acoustic_calculation():
    pass
```

Or conditionally skip:

```python
@pytest.mark.skipif(not OPENWIND_AVAILABLE, reason="OpenWind not installed")
def test_acoustic_calculation():
    pass
```

## Debugging Failed Tests

### Run in verbose mode with full output
```bash
pytest -vv -s
```

### Run only failed tests from last run
```bash
pytest --lf
```

### Drop into debugger on failure
```bash
pytest --pdb
```

### Get full traceback
```bash
pytest --tb=long
```

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/)
- Project CONTRIBUTING.md for development guidelines

---

**Status**: Test infrastructure is actively being developed. Contributions welcome!
