"""Tests for external configuration file loader

外部設定ファイルローダーのテスト（YAML専用）。
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

from gateway.config_loader import ConfigLoader


class TestConfigLoader:
    """ConfigLoaderのテスト"""

    def test_load_yaml_config(self, tmp_path):
        """YAML設定ファイルの読み込みテスト"""
        yaml_content = """
core:
  environment: production
  log_level: INFO
  azure_openai:
    available_models:
      - gpt-5-mini
      - gpt-4o
plugins:
  a5m2_compatibility:
    enabled: false
"""

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(yaml_content)

        config = ConfigLoader.load_config(str(config_file))

        assert config["core"]["environment"] == "production"
        assert config["core"]["log_level"] == "INFO"
        assert "gpt-5-mini" in config["core"]["azure_openai"]["available_models"]
        assert config["plugins"]["a5m2_compatibility"]["enabled"] is False

    def test_env_var_expansion(self, tmp_path, monkeypatch):
        """環境変数展開のテスト"""
        monkeypatch.setenv("TEST_TENANT_ID", "test-tenant-123")
        monkeypatch.setenv("TEST_CLIENT_ID", "test-client-456")

        yaml_content = """
core:
  auth:
    tenant_id: ${TEST_TENANT_ID}
    client_id: ${TEST_CLIENT_ID}
"""

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(yaml_content)

        config = ConfigLoader.load_config(str(config_file))

        assert config["core"]["auth"]["tenant_id"] == "test-tenant-123"
        assert config["core"]["auth"]["client_id"] == "test-client-456"

    def test_env_var_expansion_missing(self, tmp_path):
        """存在しない環境変数の展開テスト"""
        yaml_content = """
core:
  auth:
    tenant_id: ${NONEXISTENT_VAR}
"""

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(yaml_content)

        config = ConfigLoader.load_config(str(config_file))

        # 存在しない環境変数は空文字列になる
        assert config["core"]["auth"]["tenant_id"] == ""

    def test_auto_create_from_template(self, tmp_path, monkeypatch):
        """テンプレートからの自動生成テスト"""
        monkeypatch.chdir(tmp_path)

        # テンプレートを作成
        template_content = """
core:
  environment: development
  azure_openai:
    endpoint: ${AZURE_OPENAI_ENDPOINT}
    available_models:
      - gpt-5-mini
"""
        template_file = tmp_path / "config.yaml.template"
        with open(template_file, 'w') as f:
            f.write(template_content)

        # config.yamlが存在しないことを確認
        config_file = tmp_path / "config.yaml"
        assert not config_file.exists()

        # 自動生成を有効にして読み込み
        config = ConfigLoader.load_config(auto_create=True)

        # ファイルが作成されたことを確認
        assert config_file.exists()

        # 内容が正しいことを確認
        assert config["core"]["environment"] == "development"
        assert "gpt-5-mini" in config["core"]["azure_openai"]["available_models"]

    def test_auto_create_minimal_config(self, tmp_path, monkeypatch):
        """ミニマル設定の自動生成テスト（テンプレートなし）"""
        monkeypatch.chdir(tmp_path)

        # config.yamlが存在しないことを確認
        config_file = tmp_path / "config.yaml"
        assert not config_file.exists()

        # 自動生成を有効にして読み込み
        config = ConfigLoader.load_config(auto_create=True)

        # ファイルが作成されたことを確認
        assert config_file.exists()

        # ミニマルな設定が含まれていることを確認
        assert "core" in config
        assert "azure_openai" in config["core"]
        assert "auth" in config["core"]
        assert "plugins" in config

    def test_no_auto_create(self, tmp_path, monkeypatch):
        """自動生成を無効にした場合のテスト"""
        monkeypatch.chdir(tmp_path)

        # config.yamlが存在しないことを確認
        config_file = tmp_path / "config.yaml"
        assert not config_file.exists()

        # 自動生成を無効にして読み込み
        config = ConfigLoader.load_config(auto_create=False)

        # ファイルは作成されない
        assert not config_file.exists()

        # 空の辞書が返される
        assert config == {}

    def test_merge_configs(self):
        """設定マージのテスト"""
        base = {
            "a": 1,
            "b": {
                "c": 2,
                "d": 3
            },
            "e": [1, 2, 3]
        }

        override = {
            "a": 10,
            "b": {
                "c": 20,
                "f": 4
            },
            "g": 5
        }

        merged = ConfigLoader.merge_configs(base, override)

        assert merged["a"] == 10  # 上書き
        assert merged["b"]["c"] == 20  # ネスト内も上書き
        assert merged["b"]["d"] == 3  # 元の値を保持
        assert merged["b"]["f"] == 4  # 新しい値を追加
        assert merged["e"] == [1, 2, 3]  # リストはそのまま
        assert merged["g"] == 5  # 新しいキーを追加

    def test_nested_env_var_expansion(self, tmp_path, monkeypatch):
        """ネストした構造での環境変数展開テスト"""
        monkeypatch.setenv("MODEL_1", "gpt-4")
        monkeypatch.setenv("MODEL_2", "gpt-35-turbo")

        yaml_content = """
core:
  azure_openai:
    available_models:
      - ${MODEL_1}
      - ${MODEL_2}
      - gpt-5-mini
"""

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(yaml_content)

        config = ConfigLoader.load_config(str(config_file))

        models = config["core"]["azure_openai"]["available_models"]
        assert models[0] == "gpt-4"
        assert models[1] == "gpt-35-turbo"
        assert models[2] == "gpt-5-mini"


class TestSettingsWithExternalConfig:
    """外部設定ファイルを使用したSettingsクラスのテスト"""

    def test_load_models_from_config(self, tmp_path, monkeypatch):
        """設定ファイルからモデルリストを読み込むテスト"""
        monkeypatch.chdir(tmp_path)

        # 環境変数をモック
        monkeypatch.setenv("TENANT_ID", "test-tenant")
        monkeypatch.setenv("CLIENT_ID", "test-client")
        monkeypatch.setenv("CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")

        yaml_content = """
core:
  azure_openai:
    available_models:
      - custom-model-1
      - custom-model-2
      - custom-model-3
"""

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(yaml_content)

        from gateway.settings import Settings

        settings = Settings(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            azure_openai_endpoint="https://test.openai.azure.com"
        )

        assert len(settings.available_models) == 3
        assert "custom-model-1" in settings.available_models
        assert "custom-model-2" in settings.available_models
        assert "custom-model-3" in settings.available_models

    def test_load_plugin_settings_from_config(self, tmp_path, monkeypatch):
        """設定ファイルからプラグイン設定を読み込むテスト"""
        monkeypatch.chdir(tmp_path)

        # 環境変数をモック
        monkeypatch.setenv("TENANT_ID", "test-tenant")
        monkeypatch.setenv("CLIENT_ID", "test-client")
        monkeypatch.setenv("CLIENT_SECRET", "test-secret")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")

        yaml_content = """
plugins:
  a5m2_compatibility:
    enabled: true
    model_aliases:
      gpt-4: my-gpt4-deployment
      gpt-3.5-turbo: my-gpt35-deployment
"""

        config_file = tmp_path / "config.yaml"
        with open(config_file, 'w') as f:
            f.write(yaml_content)

        from gateway.settings import Settings

        settings = Settings(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            azure_openai_endpoint="https://test.openai.azure.com"
        )

        assert settings.is_plugin_enabled("a5m2_compatibility")
        plugin_config = settings.get_plugin_config("a5m2_compatibility")
        assert plugin_config["model_aliases"]["gpt-4"] == "my-gpt4-deployment"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
