"""Handles Entra ID token acquisition (MSAL)

Microsoft Authentication Library (MSAL) を使用して、
クライアントクレデンシャルフローでアクセストークンを取得する。

トークンはキャッシュされ、期限切れ時に自動更新される。
"""

from msal import ConfidentialClientApplication
from gateway.settings import settings
import logging

logger = logging.getLogger(__name__)


class EntraIDAuthenticator:
    """Entra ID (Azure AD) トークン取得クラス
    
    クライアントクレデンシャルフローを使用して、
    Azure OpenAI API へのアクセストークンを取得する。
    """
    
    def __init__(self):
        """MSAL クライアントアプリケーションを初期化"""
        authority = f"https://login.microsoftonline.com/{settings.tenant_id}"
        
        self.app = ConfidentialClientApplication(
            client_id=settings.client_id,
            client_credential=settings.client_secret,
            authority=authority
        )
        
        self.scope = [settings.scope]
        logger.info(f"EntraIDAuthenticator initialized for tenant: {settings.tenant_id}")
    
    def get_token(self) -> str:
        """アクセストークンを取得
        
        まずキャッシュから取得を試み、なければ新規取得する。
        
        Returns:
            str: Bearer トークン（"Bearer "プレフィックスなし）
        
        Raises:
            Exception: トークン取得に失敗した場合
        """
        # キャッシュから取得を試みる
        result = self.app.acquire_token_silent(self.scope, account=None)
        
        if not result:
            logger.info("Token not in cache, acquiring new token")
            result = self.app.acquire_token_for_client(scopes=self.scope)
        
        if "access_token" in result:
            logger.debug("Token acquired successfully")
            return result["access_token"]
        else:
            error_msg = result.get("error_description", result.get("error", "Unknown error"))
            logger.error(f"Failed to acquire token: {error_msg}")
            raise Exception(f"Token acquisition failed: {error_msg}")


# シングルトンインスタンス
authenticator = EntraIDAuthenticator()
