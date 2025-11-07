"""Request translation and forwarding to Azure OpenAI

OpenAI 互換のリクエストを受け取り、Azure OpenAI API 形式に変換して転送する。
レスポンスをそのままクライアントに返却する。
"""

import logging
from typing import Any

import httpx

from gateway import auth
from gateway.settings import settings

logger = logging.getLogger(__name__)


class AzureOpenAIProxy:
    """Azure OpenAI へのプロキシクラス

    OpenAI 互換のリクエストを Azure OpenAI API に転送し、
    レスポンスを返す。認証トークンは自動的に付与される。
    """

    def __init__(self):
        """HTTP クライアントを初期化"""
        self.endpoint = settings.azure_openai_endpoint.rstrip("/")
        self.client = httpx.AsyncClient(timeout=120.0)
        logger.info(f"AzureOpenAIProxy initialized for endpoint: {self.endpoint}")

    async def chat_completion(self, request_data: dict[str, Any]) -> dict[str, Any]:
        """チャット補完リクエストを Azure OpenAI に転送

        Args:
            request_data: OpenAI 互換のリクエストボディ
                - model: モデル名（デプロイメント名として使用）
                - messages: メッセージ配列
                - temperature, max_tokens など

        Returns:
            Dict[str, Any]: Azure OpenAI からのレスポンス

        Raises:
            httpx.HTTPError: HTTP リクエストに失敗した場合
        """
        # トークンを取得
        token = auth.get_authenticator().get_token()

        # Azure OpenAI のデプロイメント名を取得（model フィールドから）
        original_model = request_data.get("model", "gpt-4")
        deployment_name = settings.model_mapping.get(original_model, original_model)

        logger.info(f"Model mapping: {original_model} -> {deployment_name}")

        # Azure OpenAI エンドポイント URL を構築
        # 形式: {endpoint}/openai/deployments/{deployment-id}/chat/completions?api-version=2024-02-15-preview
        url = f"{self.endpoint}/openai/deployments/{deployment_name}/chat/completions"

        # ヘッダーを構築
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # API バージョンをクエリパラメータに追加
        params = {"api-version": "2024-10-21"}

        logger.info(f"Forwarding request to Azure OpenAI: {deployment_name}")
        logger.debug(f"Request URL: {url}")

        try:
            # リクエストを転送
            response = await self.client.post(
                url, json=request_data, headers=headers, params=params
            )

            # エラーチェック
            response.raise_for_status()

            # JSON レスポンスを返却
            result = response.json()
            logger.info("Request completed successfully")
            return result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Azure OpenAI returned error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to forward request: {str(e)}")
            raise

    async def close(self):
        """HTTP クライアントをクローズ"""
        await self.client.aclose()


# シングルトンインスタンス（遅延初期化）
_proxy_instance: AzureOpenAIProxy | None = None


def get_proxy() -> AzureOpenAIProxy:
    """シングルトン proxy インスタンスを取得

    初回呼び出し時にインスタンス化し、以降は同じインスタンスを返す。
    テストでモックしやすいように関数として提供。

    Returns:
        AzureOpenAIProxy: シングルトンインスタンス
    """
    global _proxy_instance
    if _proxy_instance is None:
        _proxy_instance = AzureOpenAIProxy()
    return _proxy_instance


# 後方互換性のためのエイリアス
proxy = property(lambda self: get_proxy())
