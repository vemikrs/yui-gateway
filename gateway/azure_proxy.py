"""Request translation and forwarding to Azure OpenAI

OpenAI 互換のリクエストを受け取り、Azure OpenAI API 形式に変換して転送する。
レスポンスをそのままクライアントに返却する。
"""

import logging
from typing import Any, AsyncGenerator
import json
import uuid
from datetime import datetime

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
        deployment_name = request_data.get("model", "gpt-5-mini")

        # モデルサポートチェック
        if not settings.is_model_supported(deployment_name):
            logger.warning(
                f"Unsupported model requested: {deployment_name}. Available models: {settings.available_models}"
            )

        logger.info(f"Using deployment: {deployment_name}")

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

    async def chat_completion_stream(
        self, request_data: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any], None]:
        """ストリーミングチャット補完リクエストを Azure OpenAI に転送

        Args:
            request_data: OpenAI 互換のリクエストボディ
                - model: モデル名（デプロイメント名として使用）
                - messages: メッセージ配列
                - stream: Trueで固定
                - temperature, max_tokens など

        Yields:
            Dict[str, Any]: OpenAI互換のストリーミングチャンク

        Raises:
            httpx.HTTPError: HTTP リクエストに失敗した場合
        """
        # トークンを取得
        token = auth.get_authenticator().get_token()

        # Azure OpenAI のデプロイメント名を取得（model フィールドから）
        original_model = request_data.get("model", "gpt-4")
        # get_model_mappingメソッドを使用
        deployment_name = settings.get_model_mapping(original_model) or original_model

        logger.info(f"Streaming model mapping: {original_model} -> {deployment_name}")

        # Azure OpenAI エンドポイント URL を構築
        url = f"{self.endpoint}/openai/deployments/{deployment_name}/chat/completions"

        # ヘッダーを構築
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        # API バージョンとストリーミングパラメータ
        params = {"api-version": "2024-10-21"}

        # リクエストデータをコピーしてstream=Trueに設定
        stream_request_data = request_data.copy()
        stream_request_data["stream"] = True

        logger.info(f"Starting streaming request to Azure OpenAI: {deployment_name}")
        logger.debug(f"Streaming URL: {url}")

        try:
            # ストリーミングリクエストを開始
            async with self.client.stream(
                "POST", url, json=stream_request_data, headers=headers, params=params
            ) as response:

                # エラーチェック
                response.raise_for_status()

                # ストリームチャンクを処理
                async for line in response.aiter_lines():
                    if line.strip():
                        # SSE形式のデータをパース
                        if line.startswith("data: "):
                            data_str = line[6:]  # "data: "を除去

                            if data_str.strip() == "[DONE]":
                                logger.info("Streaming completed")
                                break

                            try:
                                # JSONチャンクをパース
                                chunk_data = json.loads(data_str)

                                # OpenAI互換形式に変換してyield
                                openai_chunk = self._convert_azure_chunk_to_openai(
                                    chunk_data
                                )
                                if openai_chunk:
                                    yield openai_chunk

                            except json.JSONDecodeError as e:
                                logger.warning(
                                    f"Failed to parse streaming chunk: {data_str}, error: {e}"
                                )
                                continue

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Azure OpenAI streaming error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to process streaming request: {str(e)}")
            raise

    def _convert_azure_chunk_to_openai(
        self, azure_chunk: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Azure OpenAIのストリーミングチャンクをOpenAI互換形式に変換

        Azure OpenAIとOpenAIのストリーミングフォーマットはほぼ同じだが、
        一部フィールドの違いを吸収する。

        Args:
            azure_chunk: Azure OpenAIからのストリーミングチャンク

        Returns:
            Dict[str, Any] | None: OpenAI互換のストリーミングチャンク
        """
        if not azure_chunk:
            return None

        # ベースのチャンク構造をコピー
        openai_chunk = azure_chunk.copy()

        # Azure OpenAI固有のフィールドをクリーンアップ、もしくは変換
        # 現在のAzure OpenAIはほぼ同じフォーマットを使用しているため
        # 特別な変換は不要だが、将来の互換性のために用意

        return openai_chunk

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
