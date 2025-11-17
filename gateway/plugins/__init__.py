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

    CRITICAL = 0  # 最優先（認証等）
    HIGH = 100  # 高優先度（セキュリティ）
    NORMAL = 500  # 通常（変換処理等）
    LOW = 800  # 低優先度（ロギング等）
    LOWEST = 1000  # 最低優先度（デバッグ等）


@dataclass
@dataclass
class PluginMetadata:
    """プラグインメタデータ"""

    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    enabled: bool = True
    priority: int = PluginPriority.NORMAL.value
    dependencies: List[str] = None
    config_schema: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


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

    async def before_request(
        self, context: PluginContext, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """リクエスト前処理（オプション）"""
        return request_data

    async def after_response(
        self, context: PluginContext, response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """レスポンス後処理（オプション）"""
        return response_data

    async def on_error(
        self, context: PluginContext, error: Exception
    ) -> Optional[Dict[str, Any]]:
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

    async def load_plugin(
        self, plugin_path: str, config: Optional[Dict[str, Any]] = None
    ) -> BasePlugin:
        """プラグインをロード"""
        try:
            # モジュールの動的インポート
            if plugin_path.endswith(".py"):
                # ファイルパスから直接ロード
                spec = importlib.util.spec_from_file_location(
                    "plugin_module", plugin_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            else:
                # パッケージ名からロード
                module = importlib.import_module(plugin_path)

            # プラグインクラスを探す
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, BasePlugin)
                    and obj != BasePlugin
                    and not inspect.isabstract(obj)
                ):
                    plugin_class = obj
                    break

            if not plugin_class:
                raise PluginLoadError(f"No valid plugin class found in {plugin_path}")

            # プラグインをインスタンス化
            plugin = plugin_class(config)

            # 設定バリデーション
            if not plugin.validate_config():
                raise PluginLoadError(
                    f"Plugin {plugin.metadata.name} configuration validation failed"
                )

            # プラグイン登録
            self.plugins[plugin.metadata.name] = plugin
            self.plugin_configs[plugin.metadata.name] = config or {}

            # タイプ別登録
            if plugin.metadata.plugin_type == PluginType.MIDDLEWARE:
                self.middleware_plugins.append(plugin)
                self.middleware_plugins.sort(key=lambda p: p.metadata.priority)
            elif plugin.metadata.plugin_type == PluginType.PROVIDER:
                self.provider_plugins[plugin.metadata.name] = plugin

            logger.info(
                f"Loaded plugin: {plugin.metadata.name} v{plugin.metadata.version}"
            )
            return plugin

        except Exception as e:
            raise PluginLoadError(f"Failed to load plugin {plugin_path}: {str(e)}")

    async def register_plugin(self, plugin: BasePlugin) -> bool:
        """プラグインインスタンスを直接登録（主にテスト用）"""
        try:
            # プラグインが既に登録されているか確認
            if plugin.metadata.name in self.plugins:
                logger.warning(f"Plugin {plugin.metadata.name} is already registered")
                return False

            # 設定バリデーション
            if not plugin.validate_config():
                raise PluginLoadError(
                    f"Plugin {plugin.metadata.name} configuration validation failed"
                )

            # プラグイン登録
            self.plugins[plugin.metadata.name] = plugin
            self.plugin_configs[plugin.metadata.name] = plugin.config

            # タイプ別登録
            if plugin.metadata.plugin_type == PluginType.MIDDLEWARE:
                self.middleware_plugins.append(plugin)
                self.middleware_plugins.sort(key=lambda p: p.metadata.priority)
            elif plugin.metadata.plugin_type == PluginType.PROVIDER:
                self.provider_plugins[plugin.metadata.name] = plugin

            logger.info(
                f"Registered plugin: {plugin.metadata.name} v{plugin.metadata.version}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to register plugin {plugin.metadata.name}: {str(e)}")
            return False

    async def unregister_plugin(self, plugin_name: str) -> bool:
        """プラグインの登録解除"""
        if plugin_name not in self.plugins:
            logger.warning(f"Plugin {plugin_name} is not registered")
            return False

        plugin = self.plugins[plugin_name]

        # シャットダウン処理
        await plugin.shutdown()

        # 登録解除
        del self.plugins[plugin_name]
        if plugin_name in self.plugin_configs:
            del self.plugin_configs[plugin_name]

        # タイプ別登録から削除
        if plugin.metadata.plugin_type == PluginType.MIDDLEWARE:
            self.middleware_plugins = [
                p for p in self.middleware_plugins if p.metadata.name != plugin_name
            ]
        elif plugin.metadata.plugin_type == PluginType.PROVIDER:
            if plugin_name in self.provider_plugins:
                del self.provider_plugins[plugin_name]

        logger.info(f"Unregistered plugin: {plugin_name}")
        return True

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
        """プラグインを初期化"""
        # 依存関係を解決
        if not self._resolve_dependencies():
            raise PluginLoadError("Failed to resolve plugin dependencies")

        # 依存関係順に初期化
        initialization_order = self._get_initialization_order()

        for plugin_name in initialization_order:
            plugin = self.plugins[plugin_name]
            try:
                await plugin.initialize()
                logger.info(f"Initialized plugin: {plugin_name}")
            except Exception as e:
                logger.error(f"Failed to initialize plugin {plugin_name}: {e}")
                raise PluginLoadError(
                    f"Plugin {plugin_name} initialization failed: {e}"
                )

        self._initialized = True

    def _resolve_dependencies(self) -> bool:
        """プラグインの依存関係を解決"""
        for plugin_name, plugin in self.plugins.items():
            if plugin.metadata.dependencies:
                for dep in plugin.metadata.dependencies:
                    if dep not in self.plugins:
                        logger.error(
                            f"Plugin {plugin_name} depends on {dep}, which is not registered"
                        )
                        return False
        return True

    def _get_initialization_order(self) -> List[str]:
        """依存関係を考慮した初期化順序を取得"""
        # トポロジカルソート
        visited = set()
        order = []

        def visit(name: str):
            if name in visited:
                return
            visited.add(name)

            plugin = self.plugins[name]
            if plugin.metadata.dependencies:
                for dep in plugin.metadata.dependencies:
                    if dep in self.plugins:
                        visit(dep)

            order.append(name)

        for plugin_name in self.plugins:
            visit(plugin_name)

        return order

    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """リクエストをミドルウェアチェーンで処理"""
        context = PluginContext(request_id=str(id(request_data)))
        return await self.execute_middleware_before(context, request_data)

    async def process_response(
        self, response_data: Dict[str, Any], request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """レスポンスをミドルウェアチェーンで処理"""
        context = PluginContext(request_id=str(id(request_data)))
        return await self.execute_middleware_after(context, response_data)

    def _check_dependencies(self):
        """プラグイン依存関係チェック"""
        for plugin in self.plugins.values():
            for dep in plugin.metadata.dependencies:
                if dep not in self.plugins:
                    logger.error(
                        f"Plugin {plugin.metadata.name} missing dependency: {dep}"
                    )
                    plugin.metadata.enabled = False

    async def execute_middleware_before(
        self, context: PluginContext, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """ミドルウェア前処理実行"""
        result = request_data
        for plugin in self.middleware_plugins:
            if plugin.metadata.enabled:
                try:
                    result = await plugin.before_request(context, result)
                except Exception as e:
                    logger.error(
                        f"Middleware {plugin.metadata.name} before_request error: {e}"
                    )
        return result

    async def execute_middleware_after(
        self, context: PluginContext, response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """ミドルウェア後処理実行"""
        result = response_data
        # 逆順で実行
        for plugin in reversed(self.middleware_plugins):
            if plugin.metadata.enabled:
                try:
                    result = await plugin.after_response(context, result)
                except Exception as e:
                    logger.error(
                        f"Middleware {plugin.metadata.name} after_response error: {e}"
                    )
        return result

    async def execute_middleware_error(
        self, context: PluginContext, error: Exception
    ) -> Optional[Dict[str, Any]]:
        """ミドルウェアエラー処理実行"""
        for plugin in self.middleware_plugins:
            if plugin.metadata.enabled:
                try:
                    result = await plugin.on_error(context, error)
                    if result is not None:
                        return result
                except Exception as e:
                    logger.error(
                        f"Middleware {plugin.metadata.name} on_error error: {e}"
                    )
        return None

    def get_plugin(self, name: str) -> Optional[BasePlugin]:
        """プラグインを名前で取得"""
        return self.plugins.get(name)

    def get_plugin_info(self, name: str) -> Optional[Dict[str, Any]]:
        """プラグイン情報を取得"""
        plugin = self.plugins.get(name)
        if not plugin:
            return None

        metadata = plugin.metadata
        return {
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "author": metadata.author,
            "plugin_type": metadata.plugin_type.value if metadata.plugin_type else None,
            "enabled": metadata.enabled,
            "priority": metadata.priority,
            "dependencies": metadata.dependencies or [],
            "is_enabled": plugin.is_enabled,
            "is_initialized": plugin.is_initialized,
        }

    def list_plugins(self) -> List[Dict[str, Any]]:
        """すべてのプラグイン情報を取得"""
        return [self.get_plugin_info(name) for name in self.plugins.keys()]

    async def enable_plugins(self):
        """すべてのプラグインを有効化"""
        for plugin in self.plugins.values():
            try:
                await plugin.enable()
            except Exception as e:
                logger.error(f"Failed to enable plugin {plugin.metadata.name}: {e}")

    async def disable_plugins(self):
        """すべてのプラグインを無効化"""
        for plugin in self.plugins.values():
            try:
                await plugin.disable()
            except Exception as e:
                logger.error(f"Failed to disable plugin {plugin.metadata.name}: {e}")

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
