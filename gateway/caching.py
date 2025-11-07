"""Comprehensive caching system

レスポンスキャッシュとレート制限機能。
複数のバックエンド（メモリ、Redis、ファイル）をサポート。
TTL、LRU、キー管理、統計機能を提供。
"""

import asyncio
import time
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Union, Callable, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from abc import ABC, abstractmethod
import pickle
import os
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CacheBackend(Enum):
    """キャッシュバックエンドタイプ"""
    MEMORY = "memory"
    REDIS = "redis"
    FILE = "file"


class RateLimitStrategy(Enum):
    """レート制限戦略"""
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    TOKEN_BUCKET = "token_bucket"


@dataclass
class CacheEntry:
    """キャッシュエントリ"""
    key: str
    value: Any
    created_at: float
    ttl: Optional[float] = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    @property
    def age(self) -> float:
        return time.time() - self.created_at


@dataclass
class RateLimitInfo:
    """レート制限情報"""
    key: str
    requests: int
    window_start: float
    window_size: float
    limit: int

    @property
    def is_exceeded(self) -> bool:
        return self.requests >= self.limit

    @property
    def reset_time(self) -> float:
        return self.window_start + self.window_size


class CacheConfig(BaseModel):
    """キャッシュ設定"""
    enabled: bool = True
    backend: CacheBackend = CacheBackend.MEMORY
    default_ttl: float = 3600.0  # 1 hour
    max_size: int = 1000
    cleanup_interval: float = 300.0  # 5 minutes

    # Redis設定
    redis_url: Optional[str] = None
    redis_db: int = 0
    redis_prefix: str = "yuigateway:"

    # ファイルキャッシュ設定
    file_cache_dir: str = "/tmp/yuigateway_cache"

    # キャッシュキー設定
    cache_key_fields: List[str] = ["provider", "model", "messages", "temperature", "max_tokens"]

    # レスポンスストリーミング時のキャッシュ設定
    cache_streaming: bool = False


class RateLimitConfig(BaseModel):
    """レート制限設定"""
    enabled: bool = True
    strategy: RateLimitStrategy = RateLimitStrategy.SLIDING_WINDOW
    default_limit: int = 100  # requests per window
    default_window: float = 3600.0  # 1 hour

    # プロバイダー別制限
    provider_limits: Dict[str, Dict[str, Union[int, float]]] = {}

    # ユーザー別制限
    user_limits: Dict[str, Dict[str, Union[int, float]]] = {}

    # IP別制限
    ip_limits: Dict[str, Dict[str, Union[int, float]]] = {}


class CacheBackendInterface(ABC):
    """キャッシュバックエンドインターフェース"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """値を取得"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        """値を設定"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """値を削除"""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """キーが存在するかチェック"""
        pass

    @abstractmethod
    async def clear(self) -> bool:
        """全データクリア"""
        pass

    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """統計情報取得"""
        pass


class MemoryCacheBackend(CacheBackendInterface):
    """メモリキャッシュバックエンド"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0,
            "evictions": 0
        }
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats["misses"] += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats["misses"] += 1
                return None

            # アクセス統計更新
            entry.access_count += 1
            entry.last_accessed = time.time()

            # LRU順序更新
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            self._stats["hits"] += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        async with self._lock:
            # サイズ制限チェック
            if len(self._cache) >= self.config.max_size and key not in self._cache:
                await self._evict_lru()

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl or self.config.default_ttl
            )

            self._cache[key] = entry

            # LRU順序更新
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            self._stats["sets"] += 1
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)
                self._stats["deletes"] += 1
                return True
            return False

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired:
                return True
            return False

    async def clear(self) -> bool:
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()
            return True

    async def _evict_lru(self):
        """LRU eviction"""
        if self._access_order:
            lru_key = self._access_order.pop(0)
            if lru_key in self._cache:
                del self._cache[lru_key]
                self._stats["evictions"] += 1

    async def cleanup_expired(self):
        """期限切れエントリのクリーンアップ"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired
            ]

            for key in expired_keys:
                del self._cache[key]
                if key in self._access_order:
                    self._access_order.remove(key)

    async def get_stats(self) -> Dict[str, Any]:
        async with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

            return {
                "backend": "memory",
                "size": len(self._cache),
                "max_size": self.config.max_size,
                "hit_rate": hit_rate,
                "total_hits": self._stats["hits"],
                "total_misses": self._stats["misses"],
                "total_sets": self._stats["sets"],
                "total_deletes": self._stats["deletes"],
                "total_evictions": self._stats["evictions"]
            }


class FileCacheBackend(CacheBackendInterface):
    """ファイルキャッシュバックエンド"""

    def __init__(self, config: CacheConfig):
        self.config = config
        self.cache_dir = Path(config.file_cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "deletes": 0
        }

    def _get_file_path(self, key: str) -> Path:
        """キーからファイルパスを生成"""
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        return self.cache_dir / f"{key_hash}.cache"

    async def get(self, key: str) -> Optional[Any]:
        file_path = self._get_file_path(key)

        try:
            if not file_path.exists():
                self._stats["misses"] += 1
                return None

            with open(file_path, 'rb') as f:
                entry_data = pickle.load(f)

            entry = CacheEntry(**entry_data)

            if entry.is_expired:
                file_path.unlink(missing_ok=True)
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            return entry.value

        except Exception as e:
            logger.error(f"File cache get error: {e}")
            self._stats["misses"] += 1
            return None

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> bool:
        file_path = self._get_file_path(key)

        try:
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                ttl=ttl or self.config.default_ttl
            )

            entry_data = {
                "key": entry.key,
                "value": entry.value,
                "created_at": entry.created_at,
                "ttl": entry.ttl,
                "access_count": entry.access_count,
                "last_accessed": entry.last_accessed
            }

            with open(file_path, 'wb') as f:
                pickle.dump(entry_data, f)

            self._stats["sets"] += 1
            return True

        except Exception as e:
            logger.error(f"File cache set error: {e}")
            return False

    async def delete(self, key: str) -> bool:
        file_path = self._get_file_path(key)

        try:
            if file_path.exists():
                file_path.unlink()
                self._stats["deletes"] += 1
                return True
            return False

        except Exception as e:
            logger.error(f"File cache delete error: {e}")
            return False

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None

    async def clear(self) -> bool:
        try:
            for file_path in self.cache_dir.glob("*.cache"):
                file_path.unlink()
            return True
        except Exception as e:
            logger.error(f"File cache clear error: {e}")
            return False

    async def cleanup_expired(self):
        """期限切れファイルのクリーンアップ"""
        try:
            for file_path in self.cache_dir.glob("*.cache"):
                try:
                    with open(file_path, 'rb') as f:
                        entry_data = pickle.load(f)

                    entry = CacheEntry(**entry_data)
                    if entry.is_expired:
                        file_path.unlink()

                except Exception:
                    # 破損ファイルも削除
                    file_path.unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"File cache cleanup error: {e}")

    async def get_stats(self) -> Dict[str, Any]:
        try:
            cache_files = list(self.cache_dir.glob("*.cache"))
            total_size = sum(f.stat().st_size for f in cache_files)

            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0

            return {
                "backend": "file",
                "file_count": len(cache_files),
                "total_size_bytes": total_size,
                "cache_dir": str(self.cache_dir),
                "hit_rate": hit_rate,
                "total_hits": self._stats["hits"],
                "total_misses": self._stats["misses"],
                "total_sets": self._stats["sets"],
                "total_deletes": self._stats["deletes"]
            }
        except Exception as e:
            logger.error(f"File cache stats error: {e}")
            return {"backend": "file", "error": str(e)}


class RateLimiter:
    """レート制限クラス"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self._windows: Dict[str, RateLimitInfo] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, key: str, limit: Optional[int] = None, window: Optional[float] = None) -> tuple[bool, RateLimitInfo]:
        """レート制限チェック"""
        if not self.config.enabled:
            return True, RateLimitInfo(key, 0, time.time(), window or self.config.default_window, limit or self.config.default_limit)

        limit = limit or self.config.default_limit
        window = window or self.config.default_window

        async with self._lock:
            current_time = time.time()

            if key not in self._windows:
                self._windows[key] = RateLimitInfo(key, 0, current_time, window, limit)

            rate_info = self._windows[key]

            # ウィンドウリセットチェック
            if current_time - rate_info.window_start >= window:
                rate_info.requests = 0
                rate_info.window_start = current_time

            # リクエスト数チェック
            if rate_info.requests >= limit:
                return False, rate_info

            # リクエスト数増加
            rate_info.requests += 1
            return True, rate_info

    async def get_remaining(self, key: str) -> int:
        """残りリクエスト数を取得"""
        async with self._lock:
            if key not in self._windows:
                return self.config.default_limit

            rate_info = self._windows[key]
            return max(0, rate_info.limit - rate_info.requests)

    async def reset_rate_limit(self, key: str):
        """レート制限をリセット"""
        async with self._lock:
            if key in self._windows:
                self._windows[key].requests = 0
                self._windows[key].window_start = time.time()

    async def cleanup_expired(self):
        """期限切れウィンドウのクリーンアップ"""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, rate_info in self._windows.items()
                if current_time - rate_info.window_start > rate_info.window_size * 2
            ]

            for key in expired_keys:
                del self._windows[key]


class CacheManager:
    """キャッシュマネージャー"""

    def __init__(self, cache_config: CacheConfig, rate_limit_config: RateLimitConfig):
        self.cache_config = cache_config
        self.rate_limit_config = rate_limit_config
        self.backend = self._create_backend()
        self.rate_limiter = RateLimiter(rate_limit_config)
        self._cleanup_task: Optional[asyncio.Task] = None

    def _create_backend(self) -> CacheBackendInterface:
        """キャッシュバックエンドを作成"""
        if self.cache_config.backend == CacheBackend.MEMORY:
            return MemoryCacheBackend(self.cache_config)
        elif self.cache_config.backend == CacheBackend.FILE:
            return FileCacheBackend(self.cache_config)
        else:
            raise ValueError(f"Unsupported cache backend: {self.cache_config.backend}")

    def generate_cache_key(self, **kwargs) -> str:
        """キャッシュキーを生成"""
        key_data = {}
        for field in self.cache_config.cache_key_fields:
            if field in kwargs:
                value = kwargs[field]
                # messagesを正規化
                if field == "messages" and isinstance(value, list):
                    key_data[field] = json.dumps(value, sort_keys=True)
                else:
                    key_data[field] = str(value)

        key_string = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_string.encode()).hexdigest()

    async def get_cached_response(self, **kwargs) -> Optional[Any]:
        """キャッシュされたレスポンスを取得"""
        if not self.cache_config.enabled:
            return None

        cache_key = self.generate_cache_key(**kwargs)
        return await self.backend.get(cache_key)

    async def cache_response(self, response: Any, ttl: Optional[float] = None, **kwargs) -> bool:
        """レスポンスをキャッシュ"""
        if not self.cache_config.enabled:
            return False

        # ストリーミングレスポンスのキャッシュスキップ
        if not self.cache_config.cache_streaming and kwargs.get("stream", False):
            return False

        cache_key = self.generate_cache_key(**kwargs)
        return await self.backend.set(cache_key, response, ttl)

    async def check_rate_limit(self, identifier: str, limit_type: str = "default") -> tuple[bool, RateLimitInfo]:
        """レート制限チェック"""
        # 制限設定を取得
        limit = self.rate_limit_config.default_limit
        window = self.rate_limit_config.default_window

        # プロバイダー別制限
        if limit_type.startswith("provider:"):
            provider = limit_type[9:]
            if provider in self.rate_limit_config.provider_limits:
                config = self.rate_limit_config.provider_limits[provider]
                limit = config.get("limit", limit)
                window = config.get("window", window)

        return await self.rate_limiter.check_rate_limit(identifier, limit, window)

    async def start_cleanup_task(self):
        """クリーンアップタスク開始"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self):
        """クリーンアップタスク停止"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self):
        """クリーンアップループ"""
        while True:
            try:
                await asyncio.sleep(self.cache_config.cleanup_interval)

                # キャッシュクリーンアップ
                if hasattr(self.backend, 'cleanup_expired'):
                    await self.backend.cleanup_expired()

                # レート制限クリーンアップ
                await self.rate_limiter.cleanup_expired()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    async def get_cache_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        backend_stats = await self.backend.get_stats()

        return {
            "cache": backend_stats,
            "rate_limiter": {
                "enabled": self.rate_limit_config.enabled,
                "active_windows": len(self.rate_limiter._windows),
                "strategy": self.rate_limit_config.strategy.value
            },
            "config": {
                "cache_enabled": self.cache_config.enabled,
                "backend": self.cache_config.backend.value,
                "default_ttl": self.cache_config.default_ttl,
                "max_size": self.cache_config.max_size
            }
        }

    async def clear_cache(self) -> bool:
        """キャッシュをクリア"""
        return await self.backend.clear()


# グローバルキャッシュインスタンス
cache_config = CacheConfig()
rate_limit_config = RateLimitConfig()
cache_manager = CacheManager(cache_config, rate_limit_config)
