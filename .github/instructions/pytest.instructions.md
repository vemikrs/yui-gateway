---
applyTo: "**/tests/**/*.py"
---

# Testing Guidelines for YuiGateway

## Test Framework
- Use `pytest` for all tests
- Use `pytest-asyncio` for async test functions
- Mark async tests with `@pytest.mark.asyncio`

## Test Structure
- Follow the Arrange-Act-Assert (AAA) pattern
- Use descriptive test names: `test_<function>_<scenario>_<expected_result>`
- Group related tests in classes (optional but recommended)

## Mocking External Services
- Mock MSAL token acquisition in `auth.py` tests
- Mock httpx responses for Azure OpenAI calls
- Never make real API calls in tests
- Use `pytest-mock` or `unittest.mock` for mocking

## Example Test Pattern
```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_chat_completion_success():
    # Arrange
    mock_response = {"choices": [{"message": {"content": "test"}}]}

    # Act
    with patch("gateway.azure_proxy.authenticator.get_token", return_value="fake_token"):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value.json.return_value = mock_response
            result = await proxy.chat_completion({"model": "gpt-4", "messages": []})

    # Assert
    assert result == mock_response
    mock_post.assert_called_once()
```

## Coverage Goals
- Test both success and error paths
- Test authentication failures (expired tokens, invalid credentials)
- Test HTTP errors from Azure OpenAI (4xx, 5xx)
- Test configuration validation (missing .env values)
- Test request/response data transformation

## Fixtures
- Create reusable fixtures in `conftest.py`
- Use fixtures for common test data (sample requests, mock responses)
- Use `autouse=True` sparingly, only for setup/teardown

## Assertions
- Use specific assertions: `assert x == y`, not `assert x`
- Use `pytest.raises()` for exception testing
- Check specific error messages, not just exception types
