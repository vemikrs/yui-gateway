"""Config loading: tenant ID, client ID, scopes, etc.

Entra ID および Azure OpenAI の認証情報を .env から読み込む。
MVP では環境変数ベースでシンプルに実装。
"""


from pydantic_settings import BaseSettings


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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# シングルトンインスタンス
settings = Settings()
