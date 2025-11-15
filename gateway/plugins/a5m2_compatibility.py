"""A5M2互換ミドルウェア

A5M2ツールのためのモデル名変換機能。
コア機能から分離されたオプション機能として提供。
"""

import logging
from typing import Dict, Any

from gateway.plugins import MiddlewarePlugin, PluginMetadata, PluginType

logger = logging.getLogger(__name__)


class A5M2CompatibilityMiddleware(MiddlewarePlugin):
    """A5M2ツール用のモデル名変換ミドルウェア

    A5M2が送信するOpenAI標準のモデル名を、実際のAzureデプロイメント名に変換します。
    この機能はオプションであり、明示的に有効化した場合のみ動作します。
    """

    def __init__(self):
        self._metadata = PluginMetadata(
            name="a5m2_compatibility",
            version="1.0.0",
            description="A5M2ツール用のモデル名変換ミドルウェア",
            author="YuiGateway Team",
            plugin_type=PluginType.MIDDLEWARE,
            priority=100,  # リクエスト処理の早い段階で実行
            dependencies=[],
            enabled=False  # デフォルトでは無効
        )
        super().__init__()

        # モデルエイリアスは設定から読み込む（デフォルトは空）
        self.model_aliases: Dict[str, str] = {}    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    async def initialize(self) -> bool:
        """プラグイン初期化"""
        logger.info("A5M2 Compatibility Middleware initialized")
        return True

    async def enable(self) -> bool:
        """プラグイン有効化"""
        logger.info("A5M2 Compatibility Middleware enabled - Model name translation active")
        return True

    async def disable(self) -> bool:
        """プラグイン無効化"""
        logger.info("A5M2 Compatibility Middleware disabled")
        return True

    async def destroy(self) -> bool:
        """プラグイン破棄"""
        return True

    async def configure(self, config: Dict[str, Any]) -> bool:
        """プラグイン設定"""
        if "model_aliases" in config:
            self.model_aliases.update(config["model_aliases"])
            logger.info(f"Updated model aliases: {self.model_aliases}")
        return True

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """リクエスト前処理: モデル名変換"""
        if not self.is_enabled:
            return request

        original_model = request.get("model")
        if original_model and original_model in self.model_aliases:
            mapped_model = self.model_aliases[original_model]
            request["model"] = mapped_model

            logger.info(f"A5M2 compatibility: Model name translated '{original_model}' → '{mapped_model}'")

            # 変換情報をコンテキストに保存（レスポンス時に使用）
            request["_a5m2_original_model"] = original_model

        return request

    async def process_response(self, response: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
        """レスポンス後処理: 元のモデル名に戻す"""
        if not self.is_enabled:
            return response

        # リクエスト時に保存された元のモデル名があれば復元
        original_model = request.get("_a5m2_original_model")
        if original_model:
            # レスポンスのmodelフィールドを元の名前に戻す
            if "model" in response:
                response["model"] = original_model
                logger.debug(f"A5M2 compatibility: Response model name restored to '{original_model}'")

        return response

    def get_alias_info(self) -> Dict[str, str]:
        """現在設定されているモデルエイリアス情報を取得"""
        return self.model_aliases.copy()

    def add_alias(self, source_model: str, target_model: str) -> None:
        """新しいモデルエイリアスを追加"""
        self.model_aliases[source_model] = target_model
        logger.info(f"Added model alias: '{source_model}' → '{target_model}'")

    def remove_alias(self, source_model: str) -> bool:
        """モデルエイリアスを削除"""
        if source_model in self.model_aliases:
            del self.model_aliases[source_model]
            logger.info(f"Removed model alias for '{source_model}'")
            return True
        return False
