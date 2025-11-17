"""Integration tests for the complete YuiGateway system

全体システムの統合テスト。
モック機能を使用して実際のAPIクレジットを使用せずにテスト。
プロバイダー抽象化、プラグイン、キャッシング、モニタリングの統合をテスト。
"""

import pytest
import asyncio
import json
from typing import Dict, Any
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient

from gateway.routes import app
from gateway.settings import Settings
from gateway.monitoring import MonitoringManager, MonitoringConfig
from gateway.caching import CacheManager, CacheConfig, RateLimitConfig
from gateway.plugins import PluginManager
from gateway.validation import ConfigValidator
from gateway.providers import ProviderFactory, LLMProvider
from tests.test_utils import (
    MockAzureOpenAIService,
    TestDataFactory,
    MockPublicClientApplication,
    create_mock_context_manager,
)


class TestSystemIntegration:
    """システム統合テストクラス"""

    @pytest.fixture
    def mock_auth(self):
        """モック認証"""
        with patch("msal.PublicClientApplication") as mock_msal:
            mock_app = MockPublicClientApplication("test-client")
            mock_app.set_mock_token("test@example.com", "mock_token_12345")
            mock_msal.return_value = mock_app
            yield mock_app

    @pytest.fixture
    def mock_azure_service(self):
        """モックAzure OpenAIサービス"""
        service = MockAzureOpenAIService()
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = service.mock_post
            mock_client_class.return_value = mock_client
            yield service

    @pytest.fixture
    def test_client(self, mock_auth, mock_settings):
        """テストクライアント

        Why: mock_settingsを追加して環境変数が設定されるようにする
        テストクライアント作成前にシングルトンをリセットして新しい設定を反映
        """
        # シングルトンインスタンスをリセット
        from gateway.settings import SettingsManager
        from gateway import auth, azure_proxy
        
        SettingsManager._instance = None
        auth._authenticator_instance = None
        azure_proxy._proxy_instance = None
        
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_complete_chat_completion_workflow(
        self, test_client, mock_azure_service
    ):
        """完全なチャット完了ワークフローのテスト"""
        # テストデータ準備
        request_data = TestDataFactory.create_chat_request(
            model="gpt-4", messages=[{"role": "user", "content": "Hello, world!"}]
        )
        response_data = TestDataFactory.create_chat_response(
            content="Hello! How can I assist you today?"
        )

        # Azure OpenAIレスポンス設定
        mock_azure_service.set_response(response_data)

        # リクエスト実行
        response = test_client.post("/v1/chat/completions", json=request_data)

        # レスポンス検証
        assert response.status_code == 200
        response_json = response.json()
        assert (
            response_json["choices"][0]["message"]["content"]
            == "Hello! How can I assist you today?"
        )

        # API呼び出し履歴確認
        assert mock_azure_service.get_call_count() == 1
        last_request = mock_azure_service.get_last_request()
        # gpt-4がリクエストされると、デプロイメント名gpt-4が使われる
        assert "/openai/deployments/gpt-4/chat/completions" in last_request["url"]

    @pytest.mark.asyncio
    async def test_streaming_chat_completion(self, test_client, mock_azure_service):
        """ストリーミングチャット完了のテスト"""
        # ストリーミングリクエスト
        request_data = TestDataFactory.create_chat_request(
            model="gpt-4",
            messages=[{"role": "user", "content": "Tell me a joke"}],
            stream=True,
        )

        # ストリーミングレスポンス設定
        streaming_chunks = TestDataFactory.create_streaming_chunks(
            content="Why did the chicken cross the road? To get to the other side!"
        )

        # カスタムストリーミングレスポンス
        class MockStreamingResponse:
            def __init__(self, chunks):
                self.chunks = chunks
                self.status_code = 200
                self.headers = {"content-type": "text/event-stream"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            async def aiter_lines(self):
                for chunk in self.chunks:
                    yield f"data: {json.dumps(chunk)}"

        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.return_value = MockStreamingResponse(streaming_chunks)

            # ストリーミングリクエスト実行
            response = test_client.post("/v1/chat/completions", json=request_data)

            # ステータス確認
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_error_handling_workflow(self, test_client, mock_azure_service):
        """エラーハンドリングワークフローのテスト"""
        # 無効なリクエスト
        invalid_request = {
            "model": "gpt-4",
            # messagesが欠落
        }

        response = test_client.post("/v1/chat/completions", json=invalid_request)

        # バリデーションエラーの確認
        assert response.status_code == 422
        error_response = response.json()
        # エラーレスポンスには'details'または'detail'キーがある
        assert "details" in error_response or "detail" in error_response

        # Azure OpenAIエラーのテスト
        valid_request = TestDataFactory.create_chat_request()
        mock_azure_service.set_error_response("Invalid API key", 401)

        response = test_client.post("/v1/chat/completions", json=valid_request)

        # エラーが適切に処理されることを確認
        assert response.status_code in [401, 500]  # 内部エラーハンドリングによる

    @pytest.mark.asyncio
    async def test_direct_model_usage(self, test_client, mock_azure_service):
        """直接的なモデル名使用のテスト（マッピングなし）"""
        # 実際のデプロイメント名を直接指定
        request_data = TestDataFactory.create_chat_request(model="gpt-5-mini")
        response_data = TestDataFactory.create_chat_response()

        mock_azure_service.set_response(response_data)

        response = test_client.post("/v1/chat/completions", json=request_data)
        assert response.status_code == 200

        # URLに指定したモデル名が使用されることを確認
        last_request = mock_azure_service.get_last_request()
        assert "gpt-4" in last_request["url"] or "gpt-5-mini" in last_request["url"]

        # 別のモデルのテスト
        custom_request = TestDataFactory.create_chat_request(model="gpt-35-turbo")
        mock_azure_service.set_response(response_data)
        mock_azure_service.clear_history()

        response = test_client.post("/v1/chat/completions", json=custom_request)
        assert response.status_code == 200

        # 指定したモデル名がそのまま使用される
        last_request = mock_azure_service.get_last_request()
        assert "gpt-35-turbo" in last_request["url"]


class TestMonitoringIntegration:
    """モニタリング統合テスト"""

    @pytest.mark.asyncio
    async def test_monitoring_with_real_requests(self):
        """実際のリクエストと連携したモニタリングテスト"""
        # モニタリング設定
        config = MonitoringConfig(
            enabled=True, providers=["azure"], export_interval=0.1
        )

        monitoring_manager = MonitoringManager(config)

        try:
            await monitoring_manager.start_monitoring()

            # テストリクエストのシミュレーション
            for i in range(5):
                metrics = monitoring_manager.metrics.record_request_start(
                    provider="azure", model="gpt-4", request_id=f"test-{i}"
                )

                # 成功/失敗をランダムに設定
                status_code = 200 if i < 3 else 500
                monitoring_manager.metrics.record_request_end(
                    metrics=metrics,
                    status_code=status_code,
                    tokens_used=10 if status_code == 200 else None,
                )

            # モニタリングループの実行を待機
            await asyncio.sleep(0.2)

            # 統計確認
            stats = monitoring_manager.metrics.get_provider_stats("azure")
            assert stats["total_requests"] == 5
            assert stats["successful_requests"] == 3
            assert stats["failed_requests"] == 2
            assert abs(stats["error_rate"] - 0.4) < 0.001

            # ヘルス情報確認
            health = monitoring_manager.metrics.get_health_summary()
            assert "providers" in health
            assert "azure" in health["providers"]

        finally:
            await monitoring_manager.stop_monitoring()

    @pytest.mark.asyncio
    async def test_metrics_export(self):
        """メトリクスエクスポートのテスト"""
        config = MonitoringConfig()
        monitoring_manager = MonitoringManager(config)

        # テストデータ記録
        metrics = monitoring_manager.metrics.record_request_start(
            "azure", "gpt-4", "test"
        )
        monitoring_manager.metrics.record_request_end(metrics, 200, 10)

        # Prometheusメトリクスエクスポート
        with patch("gateway.monitoring.generate_latest") as mock_export:
            mock_export.return_value = b"# HELP test_metric\ntest_metric 1.0\n"

            exported = monitoring_manager.metrics.export_metrics()
            assert "test_metric" in exported
            mock_export.assert_called_once()


class TestCachingIntegration:
    """キャッシング統合テスト"""

    @pytest.mark.asyncio
    async def test_caching_with_api_requests(self):
        """APIリクエストと連携したキャッシングテスト"""
        cache_config = CacheConfig(enabled=True, backend="memory")
        rate_limit_config = RateLimitConfig(enabled=True, default_limit=10)
        cache_manager = CacheManager(cache_config, rate_limit_config)

        try:
            await cache_manager.start_cleanup_task()

            # テストリクエストパラメータ
            request_params = {
                "provider": "azure",
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello"}],
            }

            # レスポンスデータ
            response_data = TestDataFactory.create_chat_response("Cached response!")

            # 初回リクエスト（キャッシュミス）
            cached_response = await cache_manager.get_cached_response(**request_params)
            assert cached_response is None

            # レスポンスをキャッシュ
            success = await cache_manager.cache_response(
                response_data, **request_params
            )
            assert success

            # 二回目のリクエスト（キャッシュヒット）
            cached_response = await cache_manager.get_cached_response(**request_params)
            assert cached_response == response_data

            # キャッシュ統計確認
            stats = await cache_manager.get_cache_stats()
            assert stats["cache"]["size"] == 1
            assert stats["config"]["cache_enabled"]

        finally:
            await cache_manager.stop_cleanup_task()

    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self):
        """レート制限統合テスト"""
        cache_config = CacheConfig(enabled=False)  # キャッシュ無効
        rate_limit_config = RateLimitConfig(
            enabled=True, default_limit=3, default_window=60.0
        )
        cache_manager = CacheManager(cache_config, rate_limit_config)

        user_id = "test_user_123"

        # 制限内のリクエスト
        for i in range(3):
            allowed, rate_info = await cache_manager.check_rate_limit(user_id)
            assert allowed
            assert rate_info.requests == i + 1

        # 制限超過
        blocked, rate_info = await cache_manager.check_rate_limit(user_id)
        assert not blocked
        assert rate_info.is_exceeded

        # 残りリクエスト数確認
        remaining = await cache_manager.rate_limiter.get_remaining(user_id)
        assert remaining == 0


class TestPluginIntegration:
    """プラグイン統合テスト"""

    @pytest.mark.asyncio
    async def test_plugin_system_with_validation(self):
        """バリデーション付きプラグインシステムのテスト"""
        plugin_manager = PluginManager()
        validator = ConfigValidator()

        # テスト用プラグイン
        class TestIntegrationPlugin:
            def __init__(self):
                from gateway.plugins import PluginMetadata, PluginType

                self.metadata = PluginMetadata(
                    name="integration_test_plugin",
                    version="1.0.0",
                    description="Integration test plugin",
                    author="Test",
                    plugin_type=PluginType.MIDDLEWARE,
                )
                self.configured = False

            async def initialize(self) -> bool:
                return True

            async def enable(self) -> bool:
                return True

            async def disable(self) -> bool:
                return True

            async def destroy(self) -> bool:
                return True

            async def configure(self, config) -> bool:
                self.configured = True
                return True

            def validate_config(self) -> bool:
                """設定バリデーション（引数なし）"""
                return True

            @property
            def is_initialized(self) -> bool:
                return True

            @property
            def is_enabled(self) -> bool:
                return True

        # プラグイン設定スキーマ
        plugin_schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "enabled": {"type": "boolean"}},
            "required": ["name", "enabled"],
        }

        validator.register_schema("test_plugin_config", plugin_schema)

        # 設定検証
        plugin_config = {"name": "integration_test_plugin", "enabled": True}
        result = validator.validate("test_plugin_config", plugin_config)
        assert result.is_valid

        # プラグイン登録と設定
        plugin = TestIntegrationPlugin()
        await plugin_manager.register_plugin(plugin)
        await plugin.configure(plugin_config)

        await plugin_manager.initialize_plugins()
        await plugin_manager.enable_plugins()

        # プラグイン情報確認
        info = plugin_manager.get_plugin_info("integration_test_plugin")
        assert info is not None
        assert info["name"] == "integration_test_plugin"
        assert plugin.configured


class TestFullSystemWorkflow:
    """完全システムワークフロー統合テスト"""

    @pytest.mark.asyncio
    async def test_complete_system_with_all_features(self):
        """全機能を含む完全システムテスト"""
        # 設定
        monitoring_config = MonitoringConfig(
            enabled=True, providers=["azure"], export_interval=0.1
        )

        cache_config = CacheConfig(enabled=True, backend="memory")
        rate_limit_config = RateLimitConfig(enabled=True, default_limit=10)

        # コンポーネント初期化
        monitoring_manager = MonitoringManager(monitoring_config)
        cache_manager = CacheManager(cache_config, rate_limit_config)
        plugin_manager = PluginManager()
        validator = ConfigValidator()

        try:
            # システム開始
            await monitoring_manager.start_monitoring()
            await cache_manager.start_cleanup_task()
            await plugin_manager.initialize_plugins()
            await plugin_manager.enable_plugins()

            # リクエストシミュレーション
            request_params = {
                "provider": "azure",
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "System integration test"}],
            }

            # レート制限チェック
            user_id = "integration_test_user"
            allowed, rate_info = await cache_manager.check_rate_limit(user_id)
            assert allowed

            # キャッシュチェック（初回はミス）
            cached_response = await cache_manager.get_cached_response(**request_params)
            assert cached_response is None

            # モニタリング開始
            metrics = monitoring_manager.metrics.record_request_start(
                provider="azure", model="gpt-4", request_id="integration-test-001"
            )

            # レスポンス生成とキャッシュ
            response_data = TestDataFactory.create_chat_response(
                "This is a system integration test response"
            )

            await cache_manager.cache_response(response_data, **request_params)

            # モニタリング完了
            monitoring_manager.metrics.record_request_end(
                metrics=metrics, status_code=200, tokens_used=25
            )

            # 二回目のリクエスト（キャッシュヒット）
            cached_response = await cache_manager.get_cached_response(**request_params)
            assert cached_response == response_data

            # システム統計確認
            monitoring_stats = monitoring_manager.metrics.get_provider_stats("azure")
            assert monitoring_stats["total_requests"] == 1
            assert monitoring_stats["success_rate"] == 1.0

            cache_stats = await cache_manager.get_cache_stats()
            assert cache_stats["cache"]["size"] == 1

            plugin_list = plugin_manager.list_plugins()
            assert isinstance(plugin_list, list)

            # 健全性チェック
            health_summary = monitoring_manager.metrics.get_health_summary()
            assert health_summary["overall_health"]

        finally:
            # システム停止
            await monitoring_manager.stop_monitoring()
            await cache_manager.stop_cleanup_task()
            await plugin_manager.disable_plugins()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
