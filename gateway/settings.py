"""Clean configuration system

クリーンアーキテクチャを重視した設定システム。
コア機能は直接的でシンプル、カスタム機能はプラグインで実装。
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from gateway.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported provider types"""
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    CLAUDE = "claude"


class ProviderSettings(BaseModel):
    """Base provider configuration"""
    type: ProviderType
    name: str
    enabled: bool = True
    timeout: float = 120.0
    retry_attempts: int = 3


class AzureOpenAISettings(ProviderSettings):
    """Azure OpenAI specific settings"""
    type: ProviderType = ProviderType.AZURE_OPENAI
    endpoint: str
    api_version: str = "2024-10-21"
    tenant_id: str
    client_id: str
    client_secret: str
    scope: str = "https://cognitiveservices.azure.com/.default"


class ModelMapping(BaseModel):
    """Dynamic model mapping configuration"""
    source_model: str
    target_model: str
    provider: str
    description: Optional[str] = None


class EndpointConfig(BaseModel):
    """API endpoint configuration"""
    path: str
    enabled: bool = True
    rate_limit: Optional[int] = None
    require_auth: bool = False


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
    environment: str = "development"

    # プロバイダー設定
    providers: Dict[str, Dict[str, Any]] = Field(default_factory=lambda: {
        "azure_openai": {
            "enabled": True,
            "endpoint": "",
            "tenant_id": "",
            "client_id": "",
            "client_secret": "",
            "models": {}
        }
    })

    # サポートされるモデルリスト（実際のAzureデプロイメント名）
    # 外部設定ファイルから読み込まれる
    available_models: List[str] = Field(default_factory=list)    # プラグイン設定（コア機能から分離されたオプション機能）
    # 外部設定ファイルから読み込まれる
    plugin_settings: Dict[str, Dict[str, Any]] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_file=[".env.local", ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"  # 将来の拡張を許可
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_external_config()
        self._migrate_legacy_settings()
        self._validate_providers()

    def _migrate_legacy_settings(self):
        """レガシー設定を新しい形式に移行"""
        if self.tenant_id and self.client_id and self.azure_openai_endpoint:
            # レガシー設定がある場合、providersに移行
            self.providers["azure_openai"].update({
                "endpoint": self.azure_openai_endpoint,
                "tenant_id": self.tenant_id,
                "client_id": self.client_id,
                "client_secret": self.client_secret or ""
            })
            logger.info("Migrated legacy settings to new provider format")

    def _load_external_config(self):
        """外部設定ファイル（YAML）から設定を読み込み"""
        try:
            # テスト中は自動生成を無効化（環境変数で制御可能）
            auto_create = os.getenv("CONFIG_AUTO_CREATE", "true").lower() == "true"
            external_config = ConfigLoader.load_config(auto_create=auto_create)

            if not external_config:
                logger.info("No external config file found, using environment variables and defaults")
                return

            # コア設定のマージ
            if "core" in external_config:
                core_config = external_config["core"]

                # 環境設定
                if "environment" in core_config:
                    self.environment = core_config["environment"]
                if "log_level" in core_config:
                    self.log_level = core_config["log_level"]

                # Azure OpenAI設定
                if "azure_openai" in core_config:
                    azure_config = core_config["azure_openai"]
                    if "available_models" in azure_config:
                        self.available_models = azure_config["available_models"]
                        logger.info(f"Loaded {len(self.available_models)} available models from config")

                # 認証設定（環境変数が優先）
                if "auth" in core_config:
                    auth_config = core_config["auth"]
                    if not self.tenant_id and "tenant_id" in auth_config:
                        self.tenant_id = auth_config["tenant_id"]
                    if not self.client_id and "client_id" in auth_config:
                        self.client_id = auth_config["client_id"]
                    if not self.client_secret and "client_secret" in auth_config:
                        self.client_secret = auth_config["client_secret"]

            # プラグイン設定のマージ
            if "plugins" in external_config:
                self.plugin_settings.update(external_config["plugins"])
                logger.info(f"Loaded {len(external_config['plugins'])} plugin configurations")

            logger.info("External configuration loaded successfully")

        except FileNotFoundError:
            logger.debug("No external config file found")
        except Exception as e:
            logger.warning(f"Failed to load external config: {e}")

    def _validate_providers(self):
        """プロバイダー設定のバリデーション"""
        for name, config in self.providers.items():
            if config.get("enabled", True):
                required_fields = self._get_required_fields(config.get("type"))
                missing_fields = [field for field in required_fields if not config.get(field)]

                if missing_fields:
                    logger.error(f"Provider {name} missing required fields: {missing_fields}")
                    config["enabled"] = False

    def _get_required_fields(self, provider_type: str) -> List[str]:
        """プロバイダータイプ別の必須フィールドを取得"""
        required_fields = {
            "azure_openai": ["endpoint", "tenant_id", "client_id", "client_secret"],
            "openai": ["api_key"],
            "claude": ["api_key"]
        }
        return required_fields.get(provider_type, [])

    def get_model_mapping(self, source_model: str, provider: Optional[str] = None) -> Optional[str]:
        """モデルマッピングを取得"""
        for mapping in self.model_mappings:
            if mapping.source_model == source_model:
                if provider is None or mapping.provider == provider:
                    return mapping.target_model
        return source_model  # マッピングがない場合はそのまま返す

    def get_enabled_providers(self) -> Dict[str, Dict[str, Any]]:
        """有効なプロバイダーのみを取得"""
        return {name: config for name, config in self.providers.items() if config.get("enabled", True)}

    def is_model_supported(self, model_name: str) -> bool:
        """指定されたモデルがサポートされているかチェック"""
        return model_name in self.available_models

    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """指定されたプラグインの設定を取得"""
        return self.plugin_settings.get(plugin_name, {})

    def is_plugin_enabled(self, plugin_name: str) -> bool:
        """指定されたプラグインが有効かチェック"""
        plugin_config = self.plugin_settings.get(plugin_name, {})
        return plugin_config.get("enabled", False)


class SettingsManager:
    """設定マネージャークラス"""

    _instance: Optional['Settings'] = None

    @classmethod
    def get_settings(cls, reload: bool = False) -> Settings:
        """設定インスタンスを取得（テストではリロード可能）"""
        if cls._instance is None or reload:
            cls._instance = Settings()
        return cls._instance

    @classmethod
    def set_settings(cls, settings: Settings):
        """テスト用の設定オーバーライド"""
        cls._instance = settings


# グローバルアクセス用のショートカット
settings = SettingsManager.get_settings()

# レガシーサポート用
def get_settings() -> Settings:
    return SettingsManager.get_settings()
