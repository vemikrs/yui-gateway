# Quick Test Guide

## Installation

```bash
# Option 1: Using Poetry (recommended)
poetry install
poetry shell

# Option 2: Using pip
pip install -r requirements-test.txt
```

## Running Tests

```bash
# All tests
pytest

# Specific file
pytest tests/test_routes.py

# Specific test
pytest tests/test_routes.py::TestHealthEndpoint::test_health_returns_healthy_status

# With verbose output
pytest -v

# With coverage
pytest --cov=gateway --cov-report=html

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Test Categories

```bash
# Unit tests only
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Integration tests
pytest -m integration
```

## Validation

```bash
# Validate test file syntax
python3 scripts/validate_tests.py

# Check code syntax
python3 -m py_compile gateway/*.py tests/*.py
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements-test.txt

# 2. Validate files
python3 scripts/validate_tests.py

# 3. Run tests
pytest -v

# 4. Check coverage
pytest --cov=gateway --cov-report=term-missing
```

## Common Issues

### ModuleNotFoundError: No module named 'gateway'

**Solution:** Run pytest from project root directory

```bash
cd /path/to/yui-gateway
pytest
```

### pytest: command not found

**Solution:** Install test dependencies

```bash
pip install -r requirements-test.txt
```

### Tests fail with import errors

**Solution:** Ensure you're using Python 3.10+

```bash
python --version  # Should be 3.10.0 or higher
```

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_settings.py     # Config tests (7 tests)
├── test_auth.py         # Auth tests (8 tests)
├── test_azure_proxy.py  # Proxy tests (11 tests)
└── test_routes.py       # API tests (20+ tests)
```

## Expected Output

```
================================ test session starts =================================
collected 46 items

tests/test_settings.py::test_settings_loads_from_env PASSED                    [  2%]
tests/test_settings.py::test_settings_default_scope PASSED                     [  4%]
...
tests/test_routes.py::TestChatCompletionsEndpoint::test_chat_completions_success PASSED [100%]

========================== 46 passed in 0.50s ===================================
```

## Coverage Goals

- Overall: 80%+
- Auth module: 90%+
- Proxy module: 90%+
- Routes: 85%+
- Settings: 80%+

## Documentation

See [tests/README.md](tests/README.md) for detailed test documentation.
