"""Plugin architecture for YuiGateway

プラグインシステムにより、コア機能を変更せずに新機能を追加可能。
- Middleware plugins (リクエスト/レスポンス処理)
- Provider plugins (新しいLLMプロバイダー)
- Feature plugins (認証、ロギング、変換等)
"""

import asyncio
import importlib
import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, Union, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PluginType(Enum):
    """プラグインタイプの定義"""
    MIDDLEWARE = "middleware"
    PROVIDER = "provider"
    TRANSFORMER = "transformer"
    AUTHENTICATOR = "authenticator"
    MONITOR = "monitor"
    CACHE = "cache"


class PluginPriority(Enum):
    """プラグイン実行優先度"""
    CRITICAL = 0    # 最優先（認証等）
    HIGH = 100      # 高優先度（セキュリティ）
    NORMAL = 500    # 通常（変換処理等）
    LOW = 800       # 低優先度（ロギング等）
    LOWEST = 1000   # 最低優先度（デバッグ等）


@dataclass
class PluginMetadata:
    """プラグインメタデータ"""
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    priority: int = PluginPriority.NORMAL.value
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    enabled: bool = True


class PluginContext:
    """プラグイン実行コンテキスト"""

    def __init__(self, request_id: str, plugin_data: Optional[Dict[str, Any]] = None):
        self.request_id = request_id
        self.plugin_data = plugin_data or {}
        self.shared_data: Dict[str, Any] = {}

    def set_data(self, key: str, value: Any):
        """プラグイン間でのデータ共有"""
        self.shared_data[key] = value

    def get_data(self, key: str, default: Any = None) -> Any:
        """共有データの取得"""
        return self.shared_data.get(key, default)


class BasePlugin(ABC):
    """プラグインベースクラス"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.is_enabled = False
        self.is_initialized = False
        self.logger = logging.getLogger(f"plugin.{self.metadata.name}")

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """プラグインメタデータを返す"""
        pass

    async def initialize(self) -> bool:
        """プラグイン初期化（オプション）"""
        self.is_initialized = True
        return True

    async def enable(self) -> bool:
        """プラグイン有効化（オプション）"""
        self.is_enabled = True
        return True

    async def disable(self) -> bool:
        """プラグイン無効化（オプション）"""
        self.is_enabled = False
        return True

    async def shutdown(self):
        """プラグイン終了処理（オプション）"""
        self.is_initialized = False
        pass

    def validate_config(self) -> bool:
        """設定バリデーション（オプション）"""
        return True


class MiddlewarePlugin(BasePlugin):
    """ミドルウェアプラグインベースクラス"""

    async def before_request(self, context: PluginContext, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """リクエスト前処理（オプション）"""
        return request_data

    async def after_response(self, context: PluginContext, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """レスポンス後処理（オプション）"""
        return response_data

    async def on_error(self, context: PluginContext, error: Exception) -> Optional[Dict[str, Any]]:
        """エラー処理（オプション）"""
        return None


class ProviderPlugin(BasePlugin):
    """プロバイダープラグインベースクラス"""

    @abstractmethod
    async def create_provider(self, config: Dict[str, Any]) -> Any:
        """プロバイダーインスタンスを作成"""
        pass


class PluginLoadError(Exception):
    """プラグインロードエラー"""
    pass


class PluginManager:
    """プラグインマネージャー"""

    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.middleware_plugins: List[MiddlewarePlugin] = []
        self.provider_plugins: Dict[str, ProviderPlugin] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    async def load_plugin(self, plugin_path: str, config: Optional[Dict[str, Any]] = None) -> BasePlugin:
        """プラグインをロード"""
        try:
            # モジュールの動的インポート
            if plugin_path.endswith('.py'):
                # ファイルパスから直接ロード
                spec = importlib.util.spec_from_file_location("plugin_module", plugin_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            else:
                # パッケージ名からロード
                module = importlib.import_module(plugin_path)

            # プラグインクラスを探す
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                    issubclass(obj, BasePlugin) and
                    obj != BasePlugin and
                    not inspect.isabstract(obj)):
                    plugin_class = obj
                    break

            if not plugin_class:
                raise PluginLoadError(f"No valid plugin class found in {plugin_path}")

            # プラグインをインスタンス化
            plugin = plugin_class(config)

            # 設定バリデーション
            if not plugin.validate_config():
                raise PluginLoadError(f"Plugin {plugin.metadata.name} configuration validation failed")

            # プラグイン登録
            self.plugins[plugin.metadata.name] = plugin
            self.plugin_configs[plugin.metadata.name] = config or {}

            # タイプ別登録
            if plugin.metadata.plugin_type == PluginType.MIDDLEWARE:
                self.middleware_plugins.append(plugin)
                self.middleware_plugins.sort(key=lambda p: p.metadata.priority)
            elif plugin.metadata.plugin_type == PluginType.PROVIDER:
                self.provider_plugins[plugin.metadata.name] = plugin

            logger.info(f"Loaded plugin: {plugin.metadata.name} v{plugin.metadata.version}")
            return plugin

        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin {plugin_path}: {str(e)}")

    async def load_plugins_from_directory(self, directory: Union[str, Path]):
        """ディレクトリからプラグインを一括ロード"""
        plugin_dir = Path(directory)
        if not plugin_dir.exists():
            logger.warning(f"Plugin directory not found: {directory}")
            return

        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("__"):
                continue

            try:
                await self.load_plugin(str(plugin_file))
            except PluginLoadError as e:
                logger.error(f"Failed to load plugin {plugin_file}: {e}")

    async def initialize_plugins(self):
        """すべてのプラグインを初期化"""
        if self._initialized:
            return

        # 依存関係チェック
        self._check_dependencies()

        # 初期化実行
        for plugin in self.plugins.values():
            if plugin.metadata.enabled:
                try:
                    success = await plugin.initialize()
                    if not success:
                        logger.error(f"Plugin {plugin.metadata.name} initialization failed")
                        plugin.metadata.enabled = False
                except Exception as e:
                    logger.error(f"Plugin {plugin.metadata.name} initialization error: {e}")
                    plugin.metadata.enabled = False

        self._initialized = True
        logger.info(f"Initialized {len([p for p in self.plugins.values() if p.metadata.enabled])} plugins")

    def _check_dependencies(self):
        """プラグイン依存関係チェック"""
        for plugin in self.plugins.values():
            for dep in plugin.metadata.dependencies:
                if dep not in self.plugins:
                    logger.error(f"Plugin {plugin.metadata.name} missing dependency: {dep}")
                    plugin.metadata.enabled = False

    async def execute_middleware_before(self, context: PluginContext, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """ミドルウェア前処理実行"""
        result = request_data
        for plugin in self.middleware_plugins:
            if plugin.metadata.enabled:
                try:
                    result = await plugin.before_request(context, result)
                except Exception as e:
                    logger.error(f"Middleware {plugin.metadata.name} before_request error: {e}")
        return result

    async def execute_middleware_after(self, context: PluginContext, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """ミドルウェア後処理実行"""
        result = response_data
        # 逆順で実行
        for plugin in reversed(self.middleware_plugins):
            if plugin.metadata.enabled:
                try:
                    result = await plugin.after_response(context, result)
                except Exception as e:
                    logger.error(f"Middleware {plugin.metadata.name} after_response error: {e}")
        return result

    async def execute_middleware_error(self, context: PluginContext, error: Exception) -> Optional[Dict[str, Any]]:
        """ミドルウェアエラー処理実行"""
        for plugin in self.middleware_plugins:
            if plugin.metadata.enabled:
                try:
                    result = await plugin.on_error(context, error)
                    if result is not None:
                        return result
                except Exception as e:
                    logger.error(f"Middleware {plugin.metadata.name} on_error error: {e}")
        return None

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """プラグインを名前で取得"""
        return self.plugins.get(name)

    def list_plugins(self) -> List[PluginMetadata]:
        """すべてのプラグインメタデータを取得"""
        return [plugin.metadata for plugin in self.plugins.values()]

    async def shutdown(self):
        """すべてのプラグインを終了"""
        for plugin in self.plugins.values():
            try:
                await plugin.shutdown()
            except Exception as e:
                logger.error(f"Plugin {plugin.metadata.name} shutdown error: {e}")

        self.plugins.clear()
        self.middleware_plugins.clear()
        self.provider_plugins.clear()
        self._initialized = False


# グローバルプラグインマネージャー
plugin_manager = PluginManager()
