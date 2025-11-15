"""External configuration file loader

YAML形式の外部設定ファイルを読み込む機能。
環境変数の展開と設定の検証をサポート。
config.yamlが存在しない場合は自動生成。
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import re

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logging.warning("PyYAML not installed. Install with: pip install pyyaml")

logger = logging.getLogger(__name__)


class ConfigLoader:
    """YAML形式の外部設定ファイルローダー

    config.yamlを読み込み、環境変数を展開。
    ファイルが存在しない場合はテンプレートから自動生成。
    """

    ENV_VAR_PATTERN = re.compile(r'\$\{([^}]+)\}')

    @classmethod
    def load_config(cls, config_path: Optional[str] = None, auto_create: bool = True) -> Dict[str, Any]:
        """設定ファイルを読み込む

        Args:
            config_path: 設定ファイルのパス。Noneの場合、config.yamlを使用
            auto_create: ファイルが存在しない場合に自動生成するか

        Returns:
            設定辞書

        Raises:
            ImportError: PyYAMLがインストールされていない
        """
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML is required. Install with: pip install pyyaml")

        if config_path is None:
            config_path = "config.yaml"

        config_file = Path(config_path)

        # ファイルが存在しない場合、自動生成
        if not config_file.exists():
            if auto_create:
                logger.info(f"Config file not found. Creating {config_path} from template...")
                cls._create_default_config(config_file)
            else:
                logger.info("No config file found, using defaults")
                return {}

        # YAMLファイルを読み込み
        config = cls._load_yaml(config_file)

        # 環境変数を展開
        config = cls._expand_env_vars(config)

        logger.info(f"Loaded configuration from {config_path}")
        return config

    @classmethod
    def _create_default_config(cls, config_file: Path) -> None:
        """デフォルト設定ファイルを作成

        Args:
            config_file: 作成する設定ファイルのパス
        """
        # テンプレートからコピーを試みる
        template_path = Path("config.yaml.template")

        if template_path.exists():
            import shutil
            shutil.copy(template_path, config_file)
            logger.info(f"Created {config_file} from template")
        else:
            # テンプレートがない場合、ミニマルな設定を作成
            default_config = cls._get_minimal_config()
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            logger.info(f"Created minimal {config_file}")

    @classmethod
    def _get_minimal_config(cls) -> Dict[str, Any]:
        """ミニマルな設定を生成

        Returns:
            ミニマルな設定辞書
        """
        return {
            "core": {
                "environment": "development",
                "log_level": "INFO",
                "azure_openai": {
                    "endpoint": "${AZURE_OPENAI_ENDPOINT}",
                    "api_version": "2024-10-21",
                    "available_models": [
                        "gpt-5-mini",
                        "gpt-4o",
                        "gpt-35-turbo"
                    ]
                },
                "auth": {
                    "tenant_id": "${TENANT_ID}",
                    "client_id": "${CLIENT_ID}",
                    "client_secret": "${CLIENT_SECRET}",
                    "scope": "https://cognitiveservices.azure.com/.default"
                }
            },
            "plugins": {
                "a5m2_compatibility": {
                    "enabled": False,
                    "model_aliases": {}
                }
            }
        }

    @classmethod
    def _load_yaml(cls, file_path: Path) -> Dict[str, Any]:
        """YAMLファイルを読み込む"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    @classmethod
    def _expand_env_vars(cls, config: Any) -> Any:
        """設定内の環境変数を展開

        ${ENV_VAR_NAME} 形式の文字列を環境変数の値に置換。
        環境変数が存在しない場合は空文字列になる。

        Args:
            config: 設定値（辞書、リスト、文字列など）

        Returns:
            環境変数を展開した設定値
        """
        if isinstance(config, dict):
            return {k: cls._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [cls._expand_env_vars(item) for item in config]
        elif isinstance(config, str):
            return cls._expand_env_var_string(config)
        else:
            return config

    @classmethod
    def _expand_env_var_string(cls, text: str) -> str:
        """文字列内の環境変数を展開

        Args:
            text: 環境変数を含む可能性のある文字列

        Returns:
            環境変数を展開した文字列
        """
        def replace_env_var(match):
            env_var_name = match.group(1)
            value = os.getenv(env_var_name, '')
            if not value:
                logger.warning(f"Environment variable '{env_var_name}' is not set")
            return value

        return cls.ENV_VAR_PATTERN.sub(replace_env_var, text)

    @classmethod
    def merge_configs(cls, base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
        """設定をマージ

        override_configの値がbase_configの値を上書き。
        ネストした辞書も再帰的にマージ。

        Args:
            base_config: ベース設定
            override_config: 上書き設定

        Returns:
            マージされた設定
        """
        merged = base_config.copy()

        for key, value in override_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = cls.merge_configs(merged[key], value)
            else:
                merged[key] = value

        return merged
