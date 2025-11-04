"""Request translation and forwarding to Azure OpenAI

OpenAI 互換のリクエストを受け取り、Azure OpenAI API 形式に変換して転送する。
レスポンスをそのままクライアントに返却する。
"""

import httpx
from typing import Dict, Any
from gateway.settings import settings
from gateway.auth import authenticator
import logging

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
    
    async def chat_completion(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
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
        token = authenticator.get_token()
        
        # Azure OpenAI のデプロイメント名を取得（model フィールドから）
        deployment_name = request_data.get("model", "gpt-4")
        
        # Azure OpenAI エンドポイント URL を構築
        # 形式: {endpoint}/openai/deployments/{deployment-id}/chat/completions?api-version=2024-02-15-preview
        url = f"{self.endpoint}/openai/deployments/{deployment_name}/chat/completions"
        
        # ヘッダーを構築
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        # API バージョンをクエリパラメータに追加
        params = {
            "api-version": "2024-02-15-preview"
        }
        
        logger.info(f"Forwarding request to Azure OpenAI: {deployment_name}")
        logger.debug(f"Request URL: {url}")
        
        try:
            # リクエストを転送
            response = await self.client.post(
                url,
                json=request_data,
                headers=headers,
                params=params
            )
            
            # エラーチェック
            response.raise_for_status()
            
            # JSON レスポンスを返却
            result = response.json()
            logger.info("Request completed successfully")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Azure OpenAI returned error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to forward request: {str(e)}")
            raise
    
    async def close(self):
        """HTTP クライアントをクローズ"""
        await self.client.aclose()


# シングルトンインスタンス
proxy = AzureOpenAIProxy()
