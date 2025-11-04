"""Tests for gateway.settings module

Tests configuration loading from environment variables and .env files.
"""

import pytest
from pydantic import ValidationError


def test_settings_loads_from_env(mock_settings):
    """Test that settings load correctly from environment variables"""
    assert mock_settings.tenant_id == "00000000-0000-0000-0000-000000000000"
    assert mock_settings.client_id == "11111111-1111-1111-1111-111111111111"
    assert mock_settings.client_secret == "mock_client_secret"
    assert mock_settings.azure_openai_endpoint == "https://mock-resource.openai.azure.com"
    assert mock_settings.scope == "https://cognitiveservices.azure.com/.default"


def test_settings_default_scope(mock_tenant_id, mock_client_id, mock_client_secret, mock_azure_endpoint, monkeypatch):
    """Test that scope has a sensible default value"""
    monkeypatch.setenv("TENANT_ID", mock_tenant_id)
    monkeypatch.setenv("CLIENT_ID", mock_client_id)
    monkeypatch.setenv("CLIENT_SECRET", mock_client_secret)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", mock_azure_endpoint)
    monkeypatch.delenv("SCOPE", raising=False)
    
    from gateway import settings as settings_module
    import importlib
    importlib.reload(settings_module)
    
    assert settings_module.settings.scope == "https://cognitiveservices.azure.com/.default"


def test_settings_default_log_level(mock_settings):
    """Test that log_level has a default value"""
    assert mock_settings.log_level == "INFO"


def test_settings_custom_log_level(mock_tenant_id, mock_client_id, mock_client_secret, mock_azure_endpoint, monkeypatch):
    """Test that custom log level can be set"""
    monkeypatch.setenv("TENANT_ID", mock_tenant_id)
    monkeypatch.setenv("CLIENT_ID", mock_client_id)
    monkeypatch.setenv("CLIENT_SECRET", mock_client_secret)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", mock_azure_endpoint)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    
    from gateway import settings as settings_module
    import importlib
    importlib.reload(settings_module)
    
    assert settings_module.settings.log_level == "DEBUG"


def test_settings_missing_required_field_raises_error(monkeypatch):
    """Test that missing required fields raise validation errors"""
    # Clear all required environment variables
    for key in ["TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "AZURE_OPENAI_ENDPOINT"]:
        monkeypatch.delenv(key, raising=False)
    
    # This should raise a ValidationError when settings are reloaded
    with pytest.raises(ValidationError):
        from gateway.settings import Settings
        Settings()


def test_settings_case_insensitive(mock_tenant_id, mock_client_id, mock_client_secret, mock_azure_endpoint, monkeypatch):
    """Test that environment variables are case insensitive"""
    monkeypatch.setenv("tenant_id", mock_tenant_id)
    monkeypatch.setenv("client_id", mock_client_id)
    monkeypatch.setenv("client_secret", mock_client_secret)
    monkeypatch.setenv("azure_openai_endpoint", mock_azure_endpoint)
    
    from gateway.settings import Settings
    settings = Settings()
    
    assert settings.tenant_id == mock_tenant_id
    assert settings.client_id == mock_client_id
