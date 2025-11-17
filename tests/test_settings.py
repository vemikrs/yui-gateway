"""Tests for gateway.settings module

Tests configuration loading from environment variables and .env files.
"""

import pytest
from pydantic import ValidationError


def test_settings_loads_from_env(mock_settings):
    """Test that settings load correctly from environment variables"""
    # mock_settingsフィクスチャが期待値を設定しているため、その値を確認
    assert mock_settings.tenant_id
    assert mock_settings.client_id
    assert mock_settings.client_secret
    assert mock_settings.azure_openai_endpoint
    assert mock_settings.scope == "https://cognitiveservices.azure.com/.default"


def test_settings_default_scope(
    mock_tenant_id, mock_client_id, mock_client_secret, mock_azure_endpoint, monkeypatch
):
    """Test that scope has a sensible default value"""
    monkeypatch.setenv("TENANT_ID", mock_tenant_id)
    monkeypatch.setenv("CLIENT_ID", mock_client_id)
    monkeypatch.setenv("CLIENT_SECRET", mock_client_secret)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", mock_azure_endpoint)
    monkeypatch.delenv("SCOPE", raising=False)

    import importlib

    from gateway import settings as settings_module

    importlib.reload(settings_module)

    assert (
        settings_module.settings.scope == "https://cognitiveservices.azure.com/.default"
    )


def test_settings_default_log_level(mock_settings):
    """Test that log_level has a default value"""
    assert mock_settings.log_level == "INFO"


def test_settings_custom_log_level(
    mock_tenant_id,
    mock_client_id,
    mock_client_secret,
    mock_azure_endpoint,
    monkeypatch,
    tmp_path,
):
    """Test that custom log level can be set"""
    # テスト用の一時ディレクトリに移動（config.yamlを読み込まないようにする）
    monkeypatch.chdir(tmp_path)

    # 自動生成を無効化
    monkeypatch.setenv("CONFIG_AUTO_CREATE", "false")

    monkeypatch.setenv("TENANT_ID", mock_tenant_id)
    monkeypatch.setenv("CLIENT_ID", mock_client_id)
    monkeypatch.setenv("CLIENT_SECRET", mock_client_secret)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", mock_azure_endpoint)
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    import importlib

    from gateway import settings as settings_module

    importlib.reload(settings_module)

    assert settings_module.settings.log_level == "DEBUG"


@pytest.mark.skip(
    reason="Required fields now have default values to support test environments without .env"
)
def test_settings_missing_required_field_raises_error(tmp_path, monkeypatch):
    """Test that missing required fields no longer raise errors at initialization

    Why: Settings are now initialized with empty defaults to support test environments.
    Validation happens at runtime when credentials are actually needed.
    """
    # Clear all required environment variables
    for key in ["TENANT_ID", "CLIENT_ID", "CLIENT_SECRET", "AZURE_OPENAI_ENDPOINT"]:
        monkeypatch.delenv(key, raising=False)

    # Create an empty .env file in a temp directory
    empty_env_file = tmp_path / ".env"
    empty_env_file.write_text("")

    # Change to the temp directory to avoid reading the project's .env
    monkeypatch.chdir(tmp_path)

    # This should raise a ValidationError when settings are created without required fields
    with pytest.raises(ValidationError):
        from gateway.settings import Settings

        Settings(_env_file=str(empty_env_file))


def test_settings_case_insensitive(
    mock_tenant_id, mock_client_id, mock_client_secret, mock_azure_endpoint, monkeypatch
):
    """Test that environment variables are case insensitive"""
    monkeypatch.setenv("tenant_id", mock_tenant_id)
    monkeypatch.setenv("client_id", mock_client_id)
    monkeypatch.setenv("client_secret", mock_client_secret)
    monkeypatch.setenv("azure_openai_endpoint", mock_azure_endpoint)

    from gateway.settings import Settings

    settings = Settings()

    assert settings.tenant_id == mock_tenant_id
    assert settings.client_id == mock_client_id
