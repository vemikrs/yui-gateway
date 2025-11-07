"""Config loading: tenant ID, client ID, scopes, etc.

Entra ID および Azure OpenAI の認証情報を .env から読み込む。
MVP では環境変数ベースでシンプルに実装。
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """YuiGateway 設定クラス

    .env ファイルまたは環境変数から読み込まれる。
    Azure AD (Entra ID) 認証と Azure OpenAI エンドポイントの設定を保持する。
    """

    # Entra ID 認証情報
    tenant_id: str
    client_id: str
    client_secret: str
    scope: str = "https://cognitiveservices.azure.com/.default"

    # Azure OpenAI エンドポイント
    azure_openai_endpoint: str

    # その他
    log_level: str = "INFO"

    # モデル名マッピング（OpenAI標準名 -> Azure デプロイメント名）
    model_mapping: dict[str, str] = {
        "gpt-4": "gpt-5-mini",
        "gpt-4o": "gpt-5-mini",
        "gpt-4-turbo": "gpt-5-mini",
        "gpt-3.5-turbo": "gpt-5-mini",
        "gpt-5-mini": "gpt-5-mini",  # 実際のデプロイメント名もそのまま許可
    }

    # Pydantic v2: class-based Config は非推奨。SettingsConfigDict を使用。
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


# シングルトンインスタンス
settings = Settings()
