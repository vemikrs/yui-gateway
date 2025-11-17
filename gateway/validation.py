"""Configuration validation system

JSONSchemaベースの包括的な設定バリデーション。
プロバイダー固有のスキーマ、プラグイン設定、動的バリデーション等をサポート。
"""

import json
import logging
from typing import Any, Dict, List, Optional, Type, Union
from pathlib import Path
from enum import Enum

from pydantic import BaseModel, Field, ValidationError
from jsonschema import (
    validate,
    ValidationError as JsonSchemaValidationError,
    Draft7Validator,
)

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """バリデーションエラーの重要度"""

    ERROR = "error"  # 設定不正でサービス停止
    WARNING = "warning"  # 推奨設定でないが動作可能
    INFO = "info"  # 情報提示のみ


class ValidationResult(BaseModel):
    """バリデーション結果"""

    valid: bool
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[Dict[str, Any]] = Field(default_factory=list)
    info: List[Dict[str, Any]] = Field(default_factory=list)

    def add_issue(
        self, severity: ValidationSeverity, field: str, message: str, value: Any = None
    ):
        """バリデーション問題を追加"""
        issue = {
            "field": field,
            "message": message,
            "value": value,
            "severity": severity.value,
        }

        if severity == ValidationSeverity.ERROR:
            self.errors.append(issue)
            self.valid = False
        elif severity == ValidationSeverity.WARNING:
            self.warnings.append(issue)
        else:
            self.info.append(issue)

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def is_valid(self) -> bool:
        """バリデーション成功判定（後方互換性）"""
        return self.valid

    def summary(self) -> str:
        return f"Valid: {self.valid}, Errors: {len(self.errors)}, Warnings: {len(self.warnings)}, Info: {len(self.info)}"


class ConfigValidator:
    """設定バリデーター"""

    def __init__(self):
        self.schemas: Dict[str, Dict[str, Any]] = {}
        self.custom_validators: Dict[str, callable] = {}
        self._load_builtin_schemas()

    def _load_builtin_schemas(self):
        """組み込みスキーマの読み込み"""

        # Azure OpenAI プロバイダースキーマ
        self.schemas["azure_openai_provider"] = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["azure_openai"]},
                "name": {"type": "string", "minLength": 1},
                "enabled": {"type": "boolean"},
                "endpoint": {
                    "type": "string",
                    "pattern": r"^https://[a-zA-Z0-9\-]+\.(cognitiveservices|openai)\.azure\.com/?$",
                },
                "api_version": {
                    "type": "string",
                    "pattern": r"^\d{4}-\d{2}-\d{2}(-preview)?$",
                },
                "tenant_id": {
                    "type": "string",
                    "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                },
                "client_id": {
                    "type": "string",
                    "pattern": r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                },
                "client_secret": {"type": "string", "minLength": 1},
                "scope": {"type": "string"},
                "timeout": {"type": "number", "minimum": 1, "maximum": 300},
                "retry_attempts": {"type": "integer", "minimum": 0, "maximum": 10},
                "models": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "type",
                "name",
                "endpoint",
                "tenant_id",
                "client_id",
                "client_secret",
            ],
            "additionalProperties": False,
        }

        # OpenAI プロバイダースキーマ
        self.schemas["openai_provider"] = {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["openai"]},
                "name": {"type": "string", "minLength": 1},
                "enabled": {"type": "boolean"},
                "api_key": {"type": "string", "minLength": 1},
                "base_url": {"type": "string", "format": "uri"},
                "timeout": {"type": "number", "minimum": 1, "maximum": 300},
                "retry_attempts": {"type": "integer", "minimum": 0, "maximum": 10},
            },
            "required": ["type", "name", "api_key"],
            "additionalProperties": False,
        }

        # モデルマッピングスキーマ
        self.schemas["model_mapping"] = {
            "type": "object",
            "properties": {
                "source_model": {"type": "string", "minLength": 1},
                "target_model": {"type": "string", "minLength": 1},
                "provider": {"type": "string", "minLength": 1},
                "description": {"type": "string"},
            },
            "required": ["source_model", "target_model", "provider"],
            "additionalProperties": False,
        }

        # エンドポイント設定スキーマ
        self.schemas["endpoint_config"] = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "pattern": r"^/[a-zA-Z0-9/_\-]*$"},
                "enabled": {"type": "boolean"},
                "methods": {"type": "array", "items": {"type": "string"}},
                "rate_limit": {
                    "type": "object",
                    "properties": {
                        "requests_per_minute": {"type": "integer", "minimum": 1},
                        "burst_size": {"type": "integer", "minimum": 1},
                    },
                },
                "cache": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "ttl": {"type": "integer", "minimum": 1},
                    },
                },
                "require_auth": {"type": "boolean"},
            },
            "required": ["path"],
            "additionalProperties": False,
        }

        # キャッシュ設定スキーマ
        self.schemas["cache_config"] = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "backend": {"type": "string", "enum": ["memory", "redis", "file"]},
                "ttl": {"type": "integer", "minimum": 1},
                "max_size": {"type": "integer", "minimum": 1},
                "key_prefix": {"type": "string"},
                "redis_url": {"type": "string"},
                "file_path": {"type": "string"},
            },
            "required": ["enabled", "backend"],
        }
        # エイリアス（後方互換性）
        self.schemas["caching_config"] = self.schemas["cache_config"]

        # モニタリング設定スキーマ
        self.schemas["monitoring_config"] = {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "metrics_endpoint": {"type": "string"},
                "export_interval": {"type": "integer", "minimum": 1},
                "providers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["enabled"],
        }

    def load_schema(self, name: str, schema: Dict[str, Any]):
        """外部スキーマを読み込み"""
        self.schemas[name] = schema
        logger.info(f"Loaded validation schema: {name}")

    def load_schemas_from_file(self, file_path: Union[str, Path]):
        """ファイルからスキーマを読み込み"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                schemas = json.load(f)

            for name, schema in schemas.items():
                self.load_schema(name, schema)

        except Exception as e:
            logger.error(f"Failed to load schemas from {file_path}: {e}")

    def register_validator(self, name: str, validator_func: callable):
        """カスタムバリデーターを登録"""
        self.custom_validators[name] = validator_func
        logger.info(f"Registered custom validator: {name}")

    def register_schema(self, schema_name: str, schema: Dict[str, Any]):
        """カスタムスキーマを登録"""
        self.schemas[schema_name] = schema

    def register_custom_validator(self, schema_name: str, validator: callable):
        """カスタムバリデーター関数を登録"""
        self.custom_validators[schema_name] = validator

    def register_validator(self, schema_name: str, validator: callable):
        """カスタムバリデーター登録（後方互換性エイリアス）"""
        # スキーマレスバリデーターとして登録（空スキーマ＋カスタムバリデーター）
        self.schemas[schema_name] = {"type": "object"}
        self.custom_validators[schema_name] = validator

    def validate(self, schema_name: str, data: Dict[str, Any]) -> ValidationResult:
        """汎用バリデーションメソッド（テスト用）"""
        result = ValidationResult(valid=True)

        if schema_name not in self.schemas:
            result.add_issue(
                ValidationSeverity.ERROR, "schema", f"Unknown schema: {schema_name}"
            )
            return result

        try:
            validate(data, self.schemas[schema_name])
        except JsonSchemaValidationError as e:
            result.add_issue(
                ValidationSeverity.ERROR,
                e.path[-1] if e.path else "root",
                e.message,
                e.instance,
            )

        # カスタムバリデーション適用
        if schema_name in self.custom_validators:
            try:
                custom_result = self.custom_validators[schema_name](data)
                if isinstance(custom_result, ValidationResult):
                    # カスタムバリデーション結果をマージ
                    result.errors.extend(custom_result.errors)
                    result.warnings.extend(custom_result.warnings)
                    result.info.extend(custom_result.info)
                    if custom_result.has_errors():
                        result.valid = False
                elif not custom_result:
                    result.add_issue(
                        ValidationSeverity.ERROR, "custom", "Custom validation failed"
                    )
            except Exception as e:
                result.add_issue(
                    ValidationSeverity.ERROR,
                    "custom",
                    f"Custom validator error: {str(e)}",
                )

        return result

    def validate_provider_config(
        self, provider_config: Dict[str, Any]
    ) -> ValidationResult:
        """プロバイダー設定をバリデーション"""
        result = ValidationResult(valid=True)

        provider_type = provider_config.get("type")
        if not provider_type:
            result.add_issue(
                ValidationSeverity.ERROR, "type", "Provider type is required"
            )
            return result

        schema_name = f"{provider_type}_provider"
        if schema_name not in self.schemas:
            result.add_issue(
                ValidationSeverity.WARNING,
                "type",
                f"No validation schema found for provider type: {provider_type}",
            )
            return result

        try:
            validate(provider_config, self.schemas[schema_name])
        except JsonSchemaValidationError as e:
            result.add_issue(
                ValidationSeverity.ERROR,
                e.path[-1] if e.path else "root",
                e.message,
                e.instance,
            )

        # カスタムバリデーション
        if provider_type in self.custom_validators:
            try:
                custom_result = self.custom_validators[provider_type](provider_config)
                if isinstance(custom_result, ValidationResult):
                    result.errors.extend(custom_result.errors)
                    result.warnings.extend(custom_result.warnings)
                    result.info.extend(custom_result.info)
                    if custom_result.has_errors():
                        result.valid = False
            except Exception as e:
                result.add_issue(
                    ValidationSeverity.ERROR,
                    "custom_validation",
                    f"Custom validation failed: {str(e)}",
                )

        return result

    def validate_model_mappings(
        self, mappings: List[Dict[str, Any]]
    ) -> ValidationResult:
        """モデルマッピングをバリデーション"""
        result = ValidationResult(valid=True)

        source_models = set()
        for i, mapping in enumerate(mappings):
            # スキーマバリデーション
            try:
                validate(mapping, self.schemas["model_mapping"])
            except JsonSchemaValidationError as e:
                result.add_issue(
                    ValidationSeverity.ERROR,
                    f"mappings[{i}].{e.path[-1] if e.path else 'root'}",
                    e.message,
                )
                continue

            # 重複チェック
            source = mapping.get("source_model")
            if source in source_models:
                result.add_issue(
                    ValidationSeverity.WARNING,
                    f"mappings[{i}].source_model",
                    f"Duplicate source model: {source}",
                )
            source_models.add(source)

        return result

    def validate_endpoints(
        self, endpoints: Dict[str, Dict[str, Any]]
    ) -> ValidationResult:
        """エンドポイント設定をバリデーション"""
        result = ValidationResult(valid=True)

        paths = set()
        for name, config in endpoints.items():
            try:
                validate(config, self.schemas["endpoint_config"])
            except JsonSchemaValidationError as e:
                result.add_issue(
                    ValidationSeverity.ERROR,
                    f"endpoints.{name}.{e.path[-1] if e.path else 'root'}",
                    e.message,
                )
                continue

            # パス重複チェック
            path = config.get("path")
            if path in paths:
                result.add_issue(
                    ValidationSeverity.ERROR,
                    f"endpoints.{name}.path",
                    f"Duplicate endpoint path: {path}",
                )
            paths.add(path)

        return result

    def validate_full_config(self, config: Dict[str, Any]) -> ValidationResult:
        """完全な設定をバリデーション"""
        result = ValidationResult(valid=True)

        # プロバイダー設定
        providers = config.get("providers", {})
        for name, provider_config in providers.items():
            provider_result = self.validate_provider_config(provider_config)
            if provider_result.has_errors():
                result.valid = False
            result.errors.extend(
                [
                    {**error, "field": f"providers.{name}.{error['field']}"}
                    for error in provider_result.errors
                ]
            )
            result.warnings.extend(
                [
                    {**warning, "field": f"providers.{name}.{warning['field']}"}
                    for warning in provider_result.warnings
                ]
            )

        # モデルマッピング
        mappings = config.get("model_mappings", [])
        mapping_result = self.validate_model_mappings(mappings)
        if mapping_result.has_errors():
            result.valid = False
        result.errors.extend(mapping_result.errors)
        result.warnings.extend(mapping_result.warnings)

        # エンドポイント設定
        endpoints = config.get("endpoints", {})
        endpoint_result = self.validate_endpoints(endpoints)
        if endpoint_result.has_errors():
            result.valid = False
        result.errors.extend(endpoint_result.errors)
        result.warnings.extend(endpoint_result.warnings)

        # キャッシュ設定
        if "cache" in config:
            try:
                validate(config["cache"], self.schemas["cache_config"])
            except JsonSchemaValidationError as e:
                result.add_issue(
                    ValidationSeverity.ERROR,
                    f"cache.{e.path[-1] if e.path else 'root'}",
                    e.message,
                )

        # モニタリング設定
        if "monitoring" in config:
            try:
                validate(config["monitoring"], self.schemas["monitoring_config"])
            except JsonSchemaValidationError as e:
                result.add_issue(
                    ValidationSeverity.ERROR,
                    f"monitoring.{e.path[-1] if e.path else 'root'}",
                    e.message,
                )

        return result


# カスタムバリデーター例
def validate_azure_openai_config(config: Dict[str, Any]) -> ValidationResult:
    """Azure OpenAI設定のカスタムバリデーション"""
    result = ValidationResult(valid=True)

    # エンドポイントURLとテナントIDの整合性チェック（例）
    endpoint = config.get("endpoint", "")
    if "cognitiveservices.azure.com" in endpoint:
        if not endpoint.startswith("https://"):
            result.add_issue(
                ValidationSeverity.WARNING,
                "endpoint",
                "Azure OpenAI endpoint should use HTTPS",
            )

    # APIバージョンの推奨チェック
    api_version = config.get("api_version", "")
    if api_version and "preview" not in api_version:
        # 古いAPIバージョンの警告
        if api_version < "2024-06-01":
            result.add_issue(
                ValidationSeverity.INFO,
                "api_version",
                f"Consider updating to newer API version (current: {api_version})",
            )

    return result


# グローバルバリデーターインスタンス
config_validator = ConfigValidator()

# カスタムバリデーターの登録
config_validator.register_validator("azure_openai", validate_azure_openai_config)
