"""Pytest fixtures and configuration for YuiGateway tests

Provides shared fixtures for mocking Azure AD and Azure OpenAI services.
統合された新しいモック機能とテストユーティリティをサポート。
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from tests.test_utils import (
    MockAzureOpenAIService, TestDataFactory, MockPublicClientApplication,
    MockRedisClient, create_mock_context_manager
)


@pytest.fixture
def mock_token() -> str:
    """Mock access token for testing"""
    return "mock_access_token_12345"


@pytest.fixture
def mock_tenant_id() -> str:
    """Mock tenant ID"""
    return "00000000-0000-0000-0000-000000000000"


@pytest.fixture
def mock_client_id() -> str:
    """Mock client ID"""
    return "11111111-1111-1111-1111-111111111111"


@pytest.fixture
def mock_client_secret() -> str:
    """Mock client secret"""
    return "mock_client_secret"


@pytest.fixture
def mock_azure_endpoint() -> str:
    """Mock Azure OpenAI endpoint"""
    return "https://mock-resource.openai.azure.com"


@pytest.fixture
def mock_settings(
    mock_tenant_id, mock_client_id, mock_client_secret, mock_azure_endpoint, monkeypatch, tmp_path
):
    """Mock settings for testing"""
    # テスト用の一時ディレクトリに移動（config.yamlを読み込まないようにする）
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("TENANT_ID", mock_tenant_id)
    monkeypatch.setenv("CLIENT_ID", mock_client_id)
    monkeypatch.setenv("CLIENT_SECRET", mock_client_secret)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", mock_azure_endpoint)
    monkeypatch.setenv("SCOPE", "https://cognitiveservices.azure.com/.default")

    # Re-import settings to pick up new environment variables
    import importlib

    from gateway import settings as settings_module

    importlib.reload(settings_module)

    # Reset singleton instances for clean test state
    import gateway.auth
    import gateway.azure_proxy

    gateway.auth._authenticator_instance = None
    gateway.azure_proxy._proxy_instance = None

    return settings_module.settings


@pytest.fixture
def mock_msal_app():
    """Mock MSAL ConfidentialClientApplication"""
    app = MagicMock()
    app.acquire_token_silent.return_value = None
    app.acquire_token_for_client.return_value = {
        "access_token": "mock_access_token_12345"
    }
    return app


@pytest.fixture
def sample_chat_request() -> dict[str, Any]:
    """Sample chat completion request"""
    return {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ],
        "temperature": 0.7,
        "max_tokens": 100,
    }


@pytest.fixture
def sample_chat_response() -> dict[str, Any]:
    """Sample chat completion response from Azure OpenAI"""
    return {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "created": 1677652288,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Hello! How can I help you today?",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
    }


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient"""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_httpx_response(sample_chat_response):
    """Mock httpx Response object"""
    response = AsyncMock()
    response.status_code = 200
    response.json.return_value = sample_chat_response
    response.raise_for_status = Mock()
    return response


# 新しいモック機能のフィクスチャ

@pytest.fixture
def mock_azure_service():
    """Mock Azure OpenAI service instance"""
    return MockAzureOpenAIService()


@pytest.fixture
def test_data_factory():
    """Test data factory instance"""
    return TestDataFactory()


@pytest.fixture
def mock_msal_public_app():
    """Mock MSAL PublicClientApplication"""
    return MockPublicClientApplication("test-client-id")


@pytest.fixture
def mock_redis_client():
    """Mock Redis client"""
    return MockRedisClient()


@pytest.fixture
def sample_streaming_chunks():
    """Sample streaming response chunks"""
    return TestDataFactory.create_streaming_chunks(
        content="This is a streaming response test.",
        model="gpt-4"
    )


@pytest.fixture
def sample_error_response():
    """Sample error response"""
    return TestDataFactory.create_error_response(
        message="Invalid request parameters",
        error_type="invalid_request_error",
        code="invalid_request"
    )


@pytest.fixture(autouse=True)
def setup_test_environment():
    """自動実行されるテスト環境セットアップ"""
    # グローバルなモックインスタンスをリセット
    from tests.test_utils import mock_azure_service, mock_msal_app, mock_redis

    mock_azure_service.clear_history()
    mock_msal_app._tokens.clear()
    mock_redis.data.clear()
    mock_redis.expiry.clear()

    yield

    # テスト後クリーンアップ
    mock_azure_service.clear_history()
    mock_msal_app._tokens.clear()
    mock_redis.data.clear()
    mock_redis.expiry.clear()
