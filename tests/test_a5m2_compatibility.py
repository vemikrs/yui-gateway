"""Tests for A5M2 Compatibility Middleware

A5M2互換ミドルウェアのテスト。
コア機能から分離されたプラグイン機能として独立してテスト。
"""

import pytest
from unittest.mock import AsyncMock, patch

from gateway.plugins.a5m2_compatibility import A5M2CompatibilityMiddleware
from gateway.plugins import PluginType


class TestA5M2CompatibilityMiddleware:
    """A5M2互換ミドルウェアのテスト"""

    @pytest.fixture
    def middleware(self):
        """テスト用ミドルウェアインスタンス"""
        return A5M2CompatibilityMiddleware()

    def test_middleware_metadata(self, middleware):
        """ミドルウェアメタデータのテスト"""
        metadata = middleware.metadata
        assert metadata.name == "a5m2_compatibility"
        assert metadata.plugin_type == PluginType.MIDDLEWARE
        assert metadata.enabled is False  # デフォルトで無効
        assert metadata.priority == 100

    @pytest.mark.asyncio
    async def test_middleware_lifecycle(self, middleware):
        """ミドルウェアライフサイクルのテスト"""
        # 初期化
        assert await middleware.initialize()
        assert middleware.is_initialized

        # 有効化
        assert await middleware.enable()
        assert middleware.is_enabled

        # 無効化
        assert await middleware.disable()
        assert not middleware.is_enabled

        # 破棄
        assert await middleware.destroy()

    @pytest.mark.asyncio
    async def test_model_translation_when_enabled(self, middleware):
        """有効時のモデル名変換テスト"""
        await middleware.initialize()
        await middleware.enable()

        # gpt-4 → gpt-5-mini 変換
        request = {"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]}
        processed_request = await middleware.process_request(request)

        assert processed_request["model"] == "gpt-5-mini"
        assert processed_request["_a5m2_original_model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_model_translation_when_disabled(self, middleware):
        """無効時はモデル名変換されないテスト"""
        await middleware.initialize()
        # enable()を呼ばない = 無効状態

        request = {"model": "gpt-4", "messages": [{"role": "user", "content": "test"}]}
        processed_request = await middleware.process_request(request)

        # 変換されない
        assert processed_request["model"] == "gpt-4"
        assert "_a5m2_original_model" not in processed_request

    @pytest.mark.asyncio
    async def test_unsupported_model_passthrough(self, middleware):
        """サポートされていないモデルはそのまま通すテスト"""
        await middleware.initialize()
        await middleware.enable()

        request = {"model": "claude-3", "messages": [{"role": "user", "content": "test"}]}
        processed_request = await middleware.process_request(request)

        # 変換されずそのまま
        assert processed_request["model"] == "claude-3"
        assert "_a5m2_original_model" not in processed_request

    @pytest.mark.asyncio
    async def test_response_model_restoration(self, middleware):
        """レスポンス時の元モデル名復元テスト"""
        await middleware.initialize()
        await middleware.enable()

        # リクエスト処理
        request = {"model": "gpt-4", "_a5m2_original_model": "gpt-4"}
        response = {"model": "gpt-5-mini", "choices": [{"message": {"content": "test"}}]}

        processed_response = await middleware.process_response(response, request)

        # レスポンスのモデル名が元に戻る
        assert processed_response["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_configure_custom_aliases(self, middleware):
        """カスタムエイリアス設定のテスト"""
        await middleware.initialize()

        config = {
            "model_aliases": {
                "custom-model": "azure-custom-deployment",
                "gpt-4": "my-gpt4-deployment"  # 既存設定を上書き
            }
        }

        success = await middleware.configure(config)
        assert success

        # カスタム設定が適用される
        aliases = middleware.get_alias_info()
        assert aliases["custom-model"] == "azure-custom-deployment"
        assert aliases["gpt-4"] == "my-gpt4-deployment"  # 上書きされる

    def test_alias_management(self, middleware):
        """エイリアス管理機能のテスト"""
        # エイリアス追加
        middleware.add_alias("test-model", "azure-test")
        aliases = middleware.get_alias_info()
        assert aliases["test-model"] == "azure-test"

        # エイリアス削除
        success = middleware.remove_alias("test-model")
        assert success
        aliases = middleware.get_alias_info()
        assert "test-model" not in aliases

        # 存在しないエイリアスの削除
        success = middleware.remove_alias("nonexistent-model")
        assert not success

    @pytest.mark.asyncio
    async def test_complete_workflow(self, middleware):
        """完全なワークフローテスト"""
        await middleware.initialize()
        await middleware.enable()

        # リクエスト: A5M2が送信するOpenAI標準モデル名
        original_request = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "max_tokens": 100
        }

        # 1. リクエスト前処理（モデル名変換）
        processed_request = await middleware.process_request(original_request.copy())
        assert processed_request["model"] == "gpt-5-mini"
        assert processed_request["_a5m2_original_model"] == "gpt-4"

        # 2. Azure OpenAIからのレスポンス（変換後のモデル名）
        azure_response = {
            "model": "gpt-5-mini",
            "choices": [{"message": {"content": "Hello! How can I help?"}}],
            "usage": {"total_tokens": 20}
        }

        # 3. レスポンス後処理（元のモデル名に復元）
        final_response = await middleware.process_response(azure_response, processed_request)
        assert final_response["model"] == "gpt-4"  # A5M2が期待する名前に戻る
        assert final_response["choices"][0]["message"]["content"] == "Hello! How can I help?"


class TestA5M2MiddlewareIntegration:
    """A5M2ミドルウェアの統合テスト"""

    @pytest.mark.asyncio
    async def test_middleware_with_settings_integration(self):
        """設定システムとの統合テスト"""
        from gateway.settings import Settings

        # A5M2互換機能を有効にした設定
        settings = Settings(
            tenant_id="test-tenant",
            client_id="test-client",
            client_secret="test-secret",
            azure_openai_endpoint="https://test.openai.azure.com",
            plugin_settings={
                "a5m2_compatibility": {
                    "enabled": True,
                    "model_aliases": {
                        "gpt-4": "my-custom-gpt4"
                    }
                }
            }
        )

        # プラグイン設定の確認
        assert settings.is_plugin_enabled("a5m2_compatibility")
        plugin_config = settings.get_plugin_config("a5m2_compatibility")
        assert plugin_config["model_aliases"]["gpt-4"] == "my-custom-gpt4"

    @pytest.mark.asyncio
    async def test_logging_behavior(self):
        """ログ出力の動作テスト"""
        middleware = A5M2CompatibilityMiddleware()
        await middleware.initialize()
        await middleware.enable()

        with patch('gateway.plugins.a5m2_compatibility.logger') as mock_logger:
            request = {"model": "gpt-4"}
            await middleware.process_request(request)

            # 変換ログが出力されることを確認
            mock_logger.info.assert_called_with(
                "A5M2 compatibility: Model name translated 'gpt-4' → 'gpt-5-mini'"
            )

    def test_default_aliases(self):
        """デフォルトエイリアスの確認"""
        middleware = A5M2CompatibilityMiddleware()
        aliases = middleware.get_alias_info()

        # A5M2でよく使われるモデル名が設定されている
        expected_aliases = {
            "gpt-4": "gpt-5-mini",
            "gpt-4-turbo": "gpt-5-mini",
            "gpt-4o": "gpt-4o",
            "gpt-3.5-turbo": "gpt-35-turbo",
            "gpt-35-turbo": "gpt-35-turbo"
        }

        for source, target in expected_aliases.items():
            assert aliases[source] == target


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
