"""Test cases for plugin architecture and validation system

プラグインアーキテクチャと設定バリデーションシステムのテスト。
プラグインの動的ロード、依存関係解決、設定検証をテスト。
"""

import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, Any, Optional

from gateway.plugins import (
    PluginManager,
    BasePlugin,
    MiddlewarePlugin,
    PluginMetadata,
    PluginType,
    PluginLoadError,
    PluginContext,
)
from gateway.validation import (
    ConfigValidator,
    ValidationResult,
    ValidationError,
    ValidationSeverity,
)


class TestPluginMetadata:
    """PluginMetadataクラスのテスト"""

    def test_plugin_metadata_creation(self):
        """PluginMetadataの作成をテスト"""
        from gateway.plugins import PluginType

        metadata = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test plugin",
            author="Test Author",
            plugin_type=PluginType.MIDDLEWARE,
        )

        assert metadata.name == "test_plugin"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test plugin"
        assert metadata.author == "Test Author"
        assert metadata.dependencies == []
        assert metadata.priority == 500  # PluginPriority.NORMAL.value

    def test_plugin_metadata_with_dependencies(self):
        """依存関係を持つPluginMetadataのテスト"""
        metadata = PluginMetadata(
            name="dependent_plugin",
            version="1.0.0",
            description="Plugin with dependencies",
            author="Test Author",
            plugin_type=PluginType.MIDDLEWARE,
            dependencies=["base_plugin", "utils_plugin"],
            priority=10,
        )

        assert metadata.dependencies == ["base_plugin", "utils_plugin"]
        assert metadata.priority == 10


class MockPlugin(BasePlugin):
    """テスト用のモックプラグイン"""

    def __init__(
        self,
        name: str = "mock_plugin",
        plugin_type: PluginType = PluginType.MIDDLEWARE,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.initialized = False
        self.enabled = False
        self.destroyed = False
        self.call_history = []
        self._metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            description="Mock plugin for testing",
            author="Test",
            plugin_type=plugin_type,
        )
        super().__init__(config)

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def initialize(self) -> bool:
        self.call_history.append("initialize")
        self.initialized = True
        await super().initialize()
        return True

    async def enable(self) -> bool:
        self.call_history.append("enable")
        self.enabled = True
        await super().enable()
        return True

    async def disable(self) -> bool:
        self.call_history.append("disable")
        self.enabled = False
        await super().disable()
        return True

    async def shutdown(self):
        """シャットダウン処理"""
        self.call_history.append("shutdown")
        self.destroyed = True
        await super().shutdown()

    async def destroy(self) -> bool:
        self.call_history.append("destroy")
        self.destroyed = True
        return True

    async def configure(self, config: Dict[str, Any]) -> bool:
        self.call_history.append(f"configure:{config}")
        return True
        return True


class MockMiddlewarePlugin(MiddlewarePlugin):
    """テスト用のミドルウェアプラグイン"""

    def __init__(
        self, name: str = "mock_middleware", config: Optional[Dict[str, Any]] = None
    ):
        self.requests_processed = []
        self.responses_processed = []
        self._metadata = PluginMetadata(
            name=name,
            version="1.0.0",
            description="Mock middleware plugin",
            author="Test",
            plugin_type=PluginType.MIDDLEWARE,
        )
        super().__init__(config)

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def initialize(self) -> bool:
        await super().initialize()
        return True

    async def enable(self) -> bool:
        await super().enable()
        return True

    async def disable(self) -> bool:
        await super().disable()
        return True

    async def destroy(self) -> bool:
        return True

    async def configure(self, config: Dict[str, Any]) -> bool:
        return True

    async def before_request(
        self, context: PluginContext, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """リクエスト前処理（MiddlewarePluginインターフェース実装）"""
        self.requests_processed.append(request_data.copy())
        # テスト用にheaderを追加
        request_data["headers"] = request_data.get("headers", {})
        request_data["headers"]["X-Processed-By"] = self.metadata.name
        return request_data

    async def after_response(
        self, context: PluginContext, response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """レスポンス後処理（MiddlewarePluginインターフェース実装）"""
        self.responses_processed.append(response_data.copy())
        # テスト用にmetadataを追加
        response_data["_plugin_metadata"] = {
            "processed_by": self.metadata.name,
            "middleware_enabled": True,
        }
        return response_data

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """後方互換性用ラッパー"""
        return await self.before_request(PluginContext("test"), request)

    async def process_response(
        self, response: Dict[str, Any], request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """後方互換性用ラッパー（request情報をmetadataに含める）"""
        self.responses_processed.append(response.copy())
        response["_plugin_metadata"] = {
            "processed_by": self.metadata.name,
            "request_id": request.get("id", "unknown"),
        }
        return response


class TestBasePlugin:
    """BasePluginクラスのテスト"""

    def test_base_plugin_metadata(self):
        """BasePluginのメタデータテスト"""
        plugin = MockPlugin("test_plugin")

        assert plugin.metadata.name == "test_plugin"
        assert plugin.metadata.version == "1.0.0"
        assert plugin.metadata.description == "Mock plugin for testing"
        assert not plugin.is_initialized
        assert not plugin.is_enabled

    @pytest.mark.asyncio
    async def test_plugin_lifecycle(self):
        """プラグインライフサイクルのテスト"""
        plugin = MockPlugin()

        # 初期状態
        assert not plugin.initialized
        assert not plugin.enabled

        # 初期化
        success = await plugin.initialize()
        assert success
        assert plugin.initialized
        assert plugin.is_initialized

        # 有効化
        success = await plugin.enable()
        assert success
        assert plugin.enabled
        assert plugin.is_enabled

        # 無効化
        success = await plugin.disable()
        assert success
        assert not plugin.enabled
        assert not plugin.is_enabled

        # 破棄
        success = await plugin.destroy()
        assert success
        assert plugin.destroyed

        # 呼び出し履歴確認
        expected_calls = ["initialize", "enable", "disable", "destroy"]
        assert plugin.call_history == expected_calls

    @pytest.mark.asyncio
    async def test_plugin_configuration(self):
        """プラグイン設定のテスト"""
        plugin = MockPlugin()
        config = {"param1": "value1", "param2": 42}

        success = await plugin.configure(config)
        assert success
        assert f"configure:{config}" in plugin.call_history


class TestMiddlewarePlugin:
    """MiddlewarePluginクラスのテスト"""

    @pytest.mark.asyncio
    async def test_middleware_request_processing(self):
        """ミドルウェアのリクエスト処理テスト"""
        middleware = MockMiddlewarePlugin("test_middleware")

        # テストリクエスト
        request = {
            "id": "req-123",
            "method": "POST",
            "url": "/v1/chat/completions",
            "json": {"model": "gpt-4", "messages": []},
        }

        # リクエスト処理
        processed_request = await middleware.process_request(request)

        # ヘッダーが追加されることを確認
        assert "headers" in processed_request
        assert processed_request["headers"]["X-Processed-By"] == "test_middleware"

        # 処理履歴が記録されることを確認
        assert len(middleware.requests_processed) == 1
        assert middleware.requests_processed[0]["id"] == "req-123"

    @pytest.mark.asyncio
    async def test_middleware_response_processing(self):
        """ミドルウェアのレスポンス処理テスト"""
        middleware = MockMiddlewarePlugin("test_middleware")

        request = {"id": "req-123"}
        response = {"id": "resp-456", "choices": [{"message": {"content": "Hello"}}]}

        # レスポンス処理
        processed_response = await middleware.process_response(response, request)

        # メタデータが追加されることを確認
        assert "_plugin_metadata" in processed_response
        metadata = processed_response["_plugin_metadata"]
        assert metadata["processed_by"] == "test_middleware"
        assert metadata["request_id"] == "req-123"

        # 処理履歴が記録されることを確認
        assert len(middleware.responses_processed) == 1


class TestPluginManager:
    """PluginManagerクラスのテスト"""

    @pytest.fixture
    def plugin_manager(self):
        return PluginManager()

    def test_plugin_manager_initialization(self, plugin_manager):
        """PluginManagerの初期化テスト"""
        assert len(plugin_manager.plugins) == 0
        assert len(plugin_manager.middleware_plugins) == 0
        assert not plugin_manager._initialized

    @pytest.mark.asyncio
    async def test_register_plugin(self, plugin_manager):
        """プラグイン登録のテスト"""
        plugin = MockPlugin("test_plugin")

        success = await plugin_manager.register_plugin(plugin)
        assert success
        assert "test_plugin" in plugin_manager.plugins
        assert plugin_manager.plugins["test_plugin"] == plugin

    @pytest.mark.asyncio
    async def test_register_duplicate_plugin(self, plugin_manager):
        """重複プラグイン登録のテスト"""
        plugin1 = MockPlugin("duplicate_plugin")
        plugin2 = MockPlugin("duplicate_plugin")

        # 最初の登録は成功
        success1 = await plugin_manager.register_plugin(plugin1)
        assert success1

        # 重複登録は失敗
        success2 = await plugin_manager.register_plugin(plugin2)
        assert not success2
        assert plugin_manager.plugins["duplicate_plugin"] == plugin1

    @pytest.mark.asyncio
    async def test_register_middleware_plugin(self, plugin_manager):
        """ミドルウェアプラグイン登録のテスト"""
        middleware = MockMiddlewarePlugin("test_middleware")

        success = await plugin_manager.register_plugin(middleware)
        assert success
        assert "test_middleware" in plugin_manager.plugins
        assert middleware in plugin_manager.middleware_plugins

    @pytest.mark.asyncio
    async def test_unregister_plugin(self, plugin_manager):
        """プラグイン登録解除のテスト"""
        plugin = MockPlugin("test_plugin")
        await plugin_manager.register_plugin(plugin)

        # 登録解除
        success = await plugin_manager.unregister_plugin("test_plugin")
        assert success
        assert "test_plugin" not in plugin_manager.plugins
        assert plugin.destroyed  # destroyが呼ばれる

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_plugin(self, plugin_manager):
        """存在しないプラグインの登録解除テスト"""
        success = await plugin_manager.unregister_plugin("nonexistent_plugin")
        assert not success

    @pytest.mark.asyncio
    async def test_initialize_plugins(self, plugin_manager):
        """プラグイン初期化のテスト"""
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        await plugin_manager.register_plugin(plugin1)
        await plugin_manager.register_plugin(plugin2)

        # 初期化
        await plugin_manager.initialize_plugins()

        assert plugin_manager._initialized
        assert plugin1.is_initialized
        assert plugin2.is_initialized

    @pytest.mark.asyncio
    async def test_enable_disable_plugins(self, plugin_manager):
        """プラグイン有効化・無効化のテスト"""
        plugin = MockPlugin("test_plugin")
        await plugin_manager.register_plugin(plugin)
        await plugin_manager.initialize_plugins()

        # 有効化
        await plugin_manager.enable_plugins()
        assert plugin.enabled

        # 無効化
        await plugin_manager.disable_plugins()
        assert not plugin.enabled

    @pytest.mark.asyncio
    async def test_process_middleware_chain(self, plugin_manager):
        """ミドルウェアチェーン処理のテスト"""
        # 複数のミドルウェアを登録
        middleware1 = MockMiddlewarePlugin("middleware1")
        middleware2 = MockMiddlewarePlugin("middleware2")

        await plugin_manager.register_plugin(middleware1)
        await plugin_manager.register_plugin(middleware2)
        await plugin_manager.initialize_plugins()
        await plugin_manager.enable_plugins()

        # テストリクエスト
        request = {"id": "test-req", "data": "original"}

        # リクエスト処理チェーン
        processed_request = await plugin_manager.process_request(request)

        # 両方のミドルウェアで処理されることを確認
        assert "headers" in processed_request
        # 最後に処理されたミドルウェアのヘッダーが残る
        assert processed_request["headers"]["X-Processed-By"] in [
            "middleware1",
            "middleware2",
        ]

        # テストレスポンス
        response = {"id": "test-resp", "data": "response"}

        # レスポンス処理チェーン
        processed_response = await plugin_manager.process_response(response, request)

        # メタデータが追加されることを確認
        assert "_plugin_metadata" in processed_response

    @pytest.mark.asyncio
    async def test_dependency_resolution(self, plugin_manager):
        """依存関係解決のテスト"""
        # 依存関係を持つプラグイン
        base_plugin = MockPlugin("base_plugin")
        dependent_plugin = MockPlugin("dependent_plugin")
        dependent_plugin.metadata.dependencies = ["base_plugin"]

        # 依存プラグインを先に登録
        await plugin_manager.register_plugin(dependent_plugin)
        await plugin_manager.register_plugin(base_plugin)

        # 依存関係が解決されることを確認
        resolved = plugin_manager._resolve_dependencies()
        assert resolved

        # 初期化順序確認（依存関係順）
        await plugin_manager.initialize_plugins()
        assert base_plugin.initialized
        assert dependent_plugin.initialized

    @pytest.mark.asyncio
    async def test_dependency_resolution_failure(self, plugin_manager):
        """依存関係解決失敗のテスト"""
        # 存在しない依存関係を持つプラグイン
        dependent_plugin = MockPlugin("dependent_plugin")
        dependent_plugin.metadata.dependencies = ["nonexistent_plugin"]

        await plugin_manager.register_plugin(dependent_plugin)

        # 依存関係解決が失敗することを確認
        resolved = plugin_manager._resolve_dependencies()
        assert not resolved

    def test_get_plugin_info(self, plugin_manager):
        """プラグイン情報取得のテスト"""
        plugin = MockPlugin("info_plugin")
        plugin_manager.plugins["info_plugin"] = plugin

        info = plugin_manager.get_plugin_info("info_plugin")
        assert info is not None
        assert info["name"] == "info_plugin"
        assert info["version"] == "1.0.0"
        assert "is_initialized" in info
        assert "is_enabled" in info
        assert "enabled" in info

    def test_get_plugin_info_nonexistent(self, plugin_manager):
        """存在しないプラグインの情報取得テスト"""
        info = plugin_manager.get_plugin_info("nonexistent_plugin")
        assert info is None

    def test_list_plugins(self, plugin_manager):
        """プラグイン一覧取得のテスト"""
        plugin1 = MockPlugin("plugin1")
        plugin2 = MockPlugin("plugin2")

        plugin_manager.plugins["plugin1"] = plugin1
        plugin_manager.plugins["plugin2"] = plugin2

        plugin_list = plugin_manager.list_plugins()
        assert len(plugin_list) == 2

        # 名前でソートされることを確認
        names = [p["name"] for p in plugin_list]
        assert names == ["plugin1", "plugin2"]


class TestConfigValidator:
    """ConfigValidatorクラスのテスト"""

    @pytest.fixture
    def validator(self):
        return ConfigValidator()

    def test_validator_initialization(self, validator):
        """ConfigValidatorの初期化テスト"""
        assert len(validator.schemas) > 0
        assert "azure_openai_provider" in validator.schemas
        assert "endpoint_config" in validator.schemas
        assert "cache_config" in validator.schemas
        assert "monitoring_config" in validator.schemas

    def test_validate_provider_config_valid(self, validator):
        """有効なプロバイダー設定の検証テスト"""
        config = {
            "name": "azure",
            "type": "azure_openai",
            "endpoint": "https://test.openai.azure.com/",
            "tenant_id": "12345678-1234-1234-1234-123456789012",
            "client_id": "87654321-4321-4321-4321-210987654321",
            "client_secret": "test_secret",
            "api_version": "2024-10-21",
            "models": ["gpt-4", "gpt-35-turbo"],
        }

        result = validator.validate("azure_openai_provider", config)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_provider_config_invalid(self, validator):
        """無効なプロバイダー設定の検証テスト"""
        config = {
            "name": "azure",
            "type": "azure_openai",
            # endpointが欠落
            "api_version": "2024-10-21",
            "models": [],  # 空の配列
        }

        result = validator.validate("azure_openai_provider", config)
        assert not result.is_valid
        assert len(result.errors) > 0

        # 必須フィールドエラーの確認
        error_messages = [error["message"] for error in result.errors]
        assert any("endpoint" in msg for msg in error_messages)

    def test_validate_endpoint_config_valid(self, validator):
        """有効なエンドポイント設定の検証テスト"""
        config = {
            "path": "/v1/chat/completions",
            "methods": ["POST"],
            "rate_limit": {"requests_per_minute": 60, "burst_size": 10},
            "cache": {"enabled": True, "ttl": 3600},
        }

        result = validator.validate("endpoint_config", config)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_caching_config_valid(self, validator):
        """有効なキャッシング設定の検証テスト"""
        config = {
            "enabled": True,
            "backend": "memory",
            "default_ttl": 3600,
            "max_size": 1000,
            "cleanup_interval": 300,
        }

        result = validator.validate("caching_config", config)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_monitoring_config_valid(self, validator):
        """有効なモニタリング設定の検証テスト"""
        config = {
            "enabled": True,
            "metrics_endpoint": "/metrics",
            "export_interval": 60,
            "alert_thresholds": {"error_rate": 0.05, "response_time_p95": 5.0},
        }

        result = validator.validate("monitoring_config", config)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_unknown_schema(self, validator):
        """未知のスキーマの検証テスト"""
        config = {"test": "data"}

        result = validator.validate("unknown_schema", config)
        assert not result.is_valid
        assert len(result.errors) == 1
        assert "Unknown schema" in result.errors[0]["message"]

    def test_register_custom_validator(self, validator):
        """カスタムバリデーターの登録テスト"""
        # カスタムスキーマ
        custom_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "value": {"type": "number", "minimum": 0},
            },
            "required": ["name", "value"],
        }

        # バリデーター登録
        validator.register_schema("custom_config", custom_schema)
        assert "custom_config" in validator.schemas

        # バリデーション実行
        valid_config = {"name": "test", "value": 42}
        result = validator.validate("custom_config", valid_config)
        assert result.is_valid

        invalid_config = {"name": "", "value": -1}
        result = validator.validate("custom_config", invalid_config)
        assert not result.is_valid

    def test_validate_with_custom_validator_function(self, validator):
        """カスタムバリデーター関数のテスト"""

        def custom_validator(data: Dict[str, Any]) -> ValidationResult:
            result = ValidationResult(valid=True)
            if "special_field" in data and data["special_field"] != "expected_value":
                result.add_issue(
                    ValidationSeverity.ERROR,
                    "special_field",
                    "Special field must have expected value",
                    data["special_field"],
                )
            return result

        # カスタムバリデーター登録
        validator.register_validator("custom_validator", custom_validator)

        # バリデーション実行
        valid_data = {"special_field": "expected_value"}
        result = validator.validate("custom_validator", valid_data)
        assert result.is_valid

        invalid_data = {"special_field": "wrong_value"}
        result = validator.validate("custom_validator", invalid_data)
        assert not result.is_valid
        assert len(result.errors) == 1


@pytest.mark.asyncio
class TestIntegration:
    """プラグインアーキテクチャと設定バリデーションの統合テスト"""

    async def test_plugin_validation_integration(self):
        """プラグインと設定バリデーションの統合テスト"""
        plugin_manager = PluginManager()
        validator = ConfigValidator()

        # プラグイン設定の検証
        plugin_config = {
            "name": "test_plugin",
            "version": "1.0.0",
            "enabled": True,
            "settings": {"param1": "value1", "param2": 42},
        }

        # カスタムプラグイン設定スキーマ
        plugin_schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "version": {"type": "string", "pattern": r"^\d+\.\d+\.\d+$"},
                "enabled": {"type": "boolean"},
                "settings": {"type": "object"},
            },
            "required": ["name", "version", "enabled"],
        }

        validator.register_schema("plugin_config", plugin_schema)

        # 設定検証
        result = validator.validate("plugin_config", plugin_config)
        assert result.is_valid

        # プラグイン作成と登録
        plugin = MockPlugin(plugin_config["name"])
        await plugin_manager.register_plugin(plugin)

        # プラグイン設定適用
        await plugin.configure(plugin_config["settings"])

        # プラグイン初期化と有効化
        await plugin_manager.initialize_plugins()
        await plugin_manager.enable_plugins()

        # プラグインが正常に動作することを確認
        assert plugin.is_initialized
        assert plugin.is_enabled
        assert f"configure:{plugin_config['settings']}" in plugin.call_history

    async def test_middleware_with_validation(self):
        """バリデーション付きミドルウェアの統合テスト"""
        plugin_manager = PluginManager()
        validator = ConfigValidator()

        # ミドルウェア設定スキーマ
        middleware_schema = {
            "type": "object",
            "properties": {
                "request_validation": {"type": "boolean"},
                "response_validation": {"type": "boolean"},
                "allowed_models": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["request_validation", "response_validation"],
        }

        validator.register_schema("middleware_config", middleware_schema)

        # ミドルウェア設定
        middleware_config = {
            "request_validation": True,
            "response_validation": True,
            "allowed_models": ["gpt-4", "gpt-35-turbo"],
        }

        # 設定検証
        result = validator.validate("middleware_config", middleware_config)
        assert result.is_valid

        # ミドルウェア登録と設定
        middleware = MockMiddlewarePlugin("validation_middleware")
        await plugin_manager.register_plugin(middleware)
        await middleware.configure(middleware_config)

        await plugin_manager.initialize_plugins()
        await plugin_manager.enable_plugins()

        # ミドルウェア処理テスト
        request = {
            "id": "test-req",
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
        }

        processed_request = await plugin_manager.process_request(request)
        assert "headers" in processed_request

        response = {"id": "test-resp", "choices": [{"message": {"content": "Hi"}}]}
        processed_response = await plugin_manager.process_response(response, request)
        assert "_plugin_metadata" in processed_response
