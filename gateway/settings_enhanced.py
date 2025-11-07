"""Enhanced dynamic configuration system

拡張性と柔軟性を重視した設定システム。
複数のプロバイダー、環境別設定、動的モデルマッピングをサポート。
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported provider types"""
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"
    CLAUDE = "claude"


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


class EnhancedSettings(BaseSettings):
    """汎用性の高い YuiGateway 設定クラス

    複数のプロバイダー、動的設定、環境別構成をサポート。
    .env ファイル、環境変数、JSON設定ファイルから読み込み可能。
    """

    # サービス基本設定
    service_name: str = "YuiGateway"
    service_version: str = "0.2.0"
    environment: str = Field(default="development", description="Environment: development, staging, production")
    log_level: str = "INFO"
    debug: bool = False

    # プロバイダー設定
    providers: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "azure_openai": {
                "type": "azure_openai",
                "name": "primary",
                "enabled": True,
                "endpoint": "",  # 環境変数から設定
                "tenant_id": "",
                "client_id": "",
                "client_secret": "",
                "api_version": "2024-10-21"
            }
        }
    )

    # モデルマッピング (動的設定可能)
    model_mappings: List[ModelMapping] = Field(
        default_factory=lambda: [
            ModelMapping(source_model="gpt-4", target_model="gpt-5-mini", provider="azure_openai"),
            ModelMapping(source_model="gpt-4o", target_model="gpt-5-mini", provider="azure_openai"),
            ModelMapping(source_model="gpt-4-turbo", target_model="gpt-5-mini", provider="azure_openai"),
            ModelMapping(source_model="gpt-3.5-turbo", target_model="gpt-5-mini", provider="azure_openai"),
            ModelMapping(source_model="gpt-5-mini", target_model="gpt-5-mini", provider="azure_openai")
        ]
    )

    # APIエンドポイント設定
    endpoints: Dict[str, EndpointConfig] = Field(
        default_factory=lambda: {
            "chat_completions": EndpointConfig(path="/v1/chat/completions", enabled=True),
            "models": EndpointConfig(path="/v1/models", enabled=True),
            "health": EndpointConfig(path="/health", enabled=True)
        }
    )

    # フォールバック設定
    enable_fallback: bool = True
    fallback_order: List[str] = Field(default_factory=lambda: ["azure_openai"])

    # レガシーサポート用のフィールド
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    scope: str = "https://cognitiveservices.azure.com/.default"

    model_config = SettingsConfigDict(
        env_file=[".env.local", ".env"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"  # 将来の拡張を許可
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._migrate_legacy_settings()
        self._load_external_config()
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
        """外部設定ファイルから追加設定を読み込み"""
        config_files = [
            f"config.{self.environment}.json",
            "config.json",
            "providers.json"
        ]

        for config_file in config_files:
            config_path = Path(config_file)
            if config_path.exists():
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        external_config = json.load(f)

                    # プロバイダー設定をマージ
                    if "providers" in external_config:
                        self.providers.update(external_config["providers"])

                    # モデルマッピングをマージ
                    if "model_mappings" in external_config:
                        additional_mappings = [
                            ModelMapping(**mapping)
                            for mapping in external_config["model_mappings"]
                        ]
                        self.model_mappings.extend(additional_mappings)

                    logger.info(f"Loaded external config from {config_file}")

                except Exception as e:
                    logger.warning(f"Failed to load config from {config_file}: {e}")

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

    # レガシーサポート用プロパティ
    @property
    def model_mapping(self) -> Dict[str, str]:
        """旧いmodel_mapping形式との互換性用"""
        mapping = {}
        for m in self.model_mappings:
            mapping[m.source_model] = m.target_model
        return mapping


class SettingsManager:
    """設定マネージャークラス"""

    _instance: Optional['EnhancedSettings'] = None

    @classmethod
    def get_settings(cls, reload: bool = False) -> EnhancedSettings:
        """設定インスタンスを取得（テストではリロード可能）"""
        if cls._instance is None or reload:
            cls._instance = EnhancedSettings()
        return cls._instance

    @classmethod
    def set_settings(cls, settings: EnhancedSettings):
        """テスト用の設定オーバーライド"""
        cls._instance = settings


# レガシーサポート用のエイリアス
Settings = EnhancedSettings

# グローバルアクセス用のショートカット
settings = SettingsManager.get_settings()

# レガシーサポート用
def get_settings() -> EnhancedSettings:
    return SettingsManager.get_settings()

# 新しい設定が正しく動作することを確認
logger.info(f"YuiGateway {settings.service_version} initialized with {len(settings.get_enabled_providers())} providers")
