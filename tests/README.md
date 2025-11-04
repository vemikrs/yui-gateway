# YuiGateway Test Suite

This directory contains comprehensive tests for the YuiGateway application.

## Test Files

- **`conftest.py`** - Shared pytest fixtures and configuration
- **`test_settings.py`** - Tests for configuration loading (`gateway/settings.py`)
- **`test_auth.py`** - Tests for Entra ID authentication (`gateway/auth.py`)
- **`test_azure_proxy.py`** - Tests for Azure OpenAI proxy (`gateway/azure_proxy.py`)
- **`test_routes.py`** - Tests for FastAPI endpoints (`gateway/routes.py`)

## Running Tests

### All Tests

```bash
pytest
```

### Specific Test File

```bash
pytest tests/test_routes.py
pytest tests/test_auth.py
```

### With Coverage

```bash
pytest --cov=gateway --cov-report=html
```

### Verbose Output

```bash
pytest -v -s
```

## Test Structure

All tests follow the AAA (Arrange-Act-Assert) pattern and use pytest fixtures for setup.

### Example Test

```python
@pytest.mark.asyncio
async def test_chat_completion_success(mock_settings, mock_token, sample_chat_request):
    """Test successful chat completion request"""
    # Arrange
    with patch("gateway.azure_proxy.authenticator.get_token") as mock_get_token:
        mock_get_token.return_value = mock_token
        
        # Act
        result = await proxy.chat_completion(sample_chat_request)
        
        # Assert
        assert result["choices"][0]["message"]["content"] == "Hello!"
```

## Test Coverage

The test suite covers:

### Settings (`test_settings.py`)
- ✅ Loading from environment variables
- ✅ Default values
- ✅ Custom log levels
- ✅ Missing required fields
- ✅ Case insensitivity

### Authentication (`test_auth.py`)
- ✅ MSAL app initialization
- ✅ Token retrieval from cache
- ✅ Token acquisition on cache miss
- ✅ Authentication failures
- ✅ Error handling
- ✅ Singleton instance

### Azure Proxy (`test_azure_proxy.py`)
- ✅ HTTP client initialization
- ✅ Successful chat completions
- ✅ Custom model/deployment names
- ✅ HTTP error handling (401, 404, 500)
- ✅ Network error handling
- ✅ Token acquisition failures
- ✅ Resource cleanup
- ✅ Endpoint URL formatting

### Routes (`test_routes.py`)
- ✅ Root endpoint
- ✅ Health check endpoint
- ✅ Chat completions endpoint
- ✅ Request validation
- ✅ Optional parameters
- ✅ Error handling
- ✅ Pydantic models
- ✅ Application lifecycle

## Fixtures

Common fixtures are defined in `conftest.py`:

- `mock_token` - Mock access token
- `mock_settings` - Mock configuration with environment variables
- `mock_msal_app` - Mock MSAL application
- `sample_chat_request` - Sample OpenAI-compatible request
- `sample_chat_response` - Sample Azure OpenAI response
- `mock_httpx_client` - Mock HTTP client
- `mock_httpx_response` - Mock HTTP response

## Test Markers

```bash
# Run unit tests only
pytest -m unit

# Skip slow tests
pytest -m "not slow"

# Run integration tests
pytest -m integration
```

## Dependencies

Test dependencies are defined in `pyproject.toml`:

- `pytest` - Test framework
- `pytest-asyncio` - Async test support
- `pytest-mock` - Mocking utilities
- `pytest-cov` - Coverage reporting

## Continuous Integration

Tests are automatically run on:
- Push to main branch
- Pull requests
- Pre-commit hooks (if configured)

## Writing New Tests

When adding new functionality:

1. Create test file matching the module name (e.g., `test_new_module.py`)
2. Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
3. Group related tests in classes
4. Use fixtures from `conftest.py` or create new ones
5. Add docstrings explaining what the test validates
6. Follow the AAA pattern
7. Mock external dependencies (MSAL, Azure OpenAI, HTTP clients)

### Example New Test

```python
class TestNewFeature:
    """Tests for new feature"""
    
    def test_feature_success(self, mock_settings):
        """Test that feature works correctly"""
        # Arrange
        input_data = {"key": "value"}
        
        # Act
        result = new_feature(input_data)
        
        # Assert
        assert result["status"] == "success"
```

## Troubleshooting Tests

### Import Errors

If you see import errors, ensure:
1. All dependencies are installed: `poetry install` or `pip install -r requirements.txt`
2. The `gateway` package is in your Python path
3. You're in the project root directory

### Async Test Errors

If async tests fail:
1. Ensure `pytest-asyncio` is installed
2. Check that `asyncio_mode = "auto"` is in `pyproject.toml`
3. Mark async tests with `@pytest.mark.asyncio`

### Mock Errors

If mocking fails:
1. Verify the import path in `patch()` is correct
2. Ensure you're patching where the object is used, not where it's defined
3. Use `spec=True` for stricter mocking if needed

### Fixture Errors

If fixtures aren't found:
1. Ensure `conftest.py` is in the correct location
2. Check fixture names match usage
3. Verify fixture scope is appropriate

## Code Coverage Goals

Target coverage levels:
- Overall: 80%+
- Critical paths (auth, proxy): 90%+
- Routes: 85%+
- Settings: 80%+

## References

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio documentation](https://pytest-asyncio.readthedocs.io/)
- [Testing FastAPI](https://fastapi.tiangolo.com/tutorial/testing/)
- [GitHub Copilot testing guidelines](../.github/instructions/pytest.instructions.md)
