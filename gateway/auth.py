"""Handles Entra ID token acquisition (MSAL)

Microsoft Authentication Library (MSAL) を使用して、
クライアントクレデンシャルフローでアクセストークンを取得する。

トークンはキャッシュされ、期限切れ時に自動更新される。
"""

from msal import ConfidentialClientApplication
from gateway.settings import settings
from typing import Optional
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


# シングルトンインスタンス（遅延初期化）
_authenticator_instance: Optional[EntraIDAuthenticator] = None


def get_authenticator() -> EntraIDAuthenticator:
    """シングルトン authenticator インスタンスを取得

    初回呼び出し時にインスタンス化し、以降は同じインスタンスを返す。
    テストでモックしやすいように関数として提供。

    Returns:
        EntraIDAuthenticator: シングルトンインスタンス
    """
    global _authenticator_instance
    if _authenticator_instance is None:
        _authenticator_instance = EntraIDAuthenticator()
    return _authenticator_instance


# 後方互換性のためのエイリアス
# 使用側で get_authenticator() への移行を推奨
authenticator = property(lambda self: get_authenticator())
