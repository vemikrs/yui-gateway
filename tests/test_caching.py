"""Test cases for caching system

キャッシングシステムの包括的テスト。
レスポンスキャッシュ、レート制限、複数バックエンドをテスト。
"""

import pytest
import asyncio
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from gateway.caching import (
    CacheConfig, RateLimitConfig, CacheManager, MemoryCacheBackend, FileCacheBackend,
    RateLimiter, CacheEntry, RateLimitInfo, CacheBackend, RateLimitStrategy
)
from tests.test_utils import TestDataFactory, MockRedisClient


class TestCacheEntry:
    """CacheEntryクラスのテスト"""

    def test_cache_entry_creation(self):
        """CacheEntryの作成をテスト"""
        entry = CacheEntry(
            key="test_key",
            value={"test": "data"},
            created_at=time.time(),
            ttl=3600.0
        )

        assert entry.key == "test_key"
        assert entry.value == {"test": "data"}
        assert entry.ttl == 3600.0
        assert entry.access_count == 0

    def test_cache_entry_expiration(self):
        """キャッシュエントリの期限切れテスト"""
        # 期限切れではないエントリ
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=time.time(),
            ttl=3600.0
        )
        assert not entry.is_expired

        # 期限切れエントリ
        expired_entry = CacheEntry(
            key="expired_key",
            value="expired_value",
            created_at=time.time() - 7200,  # 2時間前
            ttl=3600.0  # 1時間のTTL
        )
        assert expired_entry.is_expired

        # TTLなし（期限切れなし）
        no_ttl_entry = CacheEntry(
            key="no_ttl_key",
            value="no_ttl_value",
            created_at=time.time() - 7200,
            ttl=None
        )
        assert not no_ttl_entry.is_expired

    def test_cache_entry_age(self):
        """キャッシュエントリの年齢計算テスト"""
        start_time = time.time()
        entry = CacheEntry(
            key="test_key",
            value="test_value",
            created_at=start_time,
            ttl=3600.0
        )

        # 少し待機
        time.sleep(0.01)

        assert entry.age > 0
        assert entry.age < 1.0  # 1秒未満


class TestMemoryCacheBackend:
    """MemoryCacheBackendクラスのテスト"""

    @pytest.fixture
    def config(self):
        return CacheConfig(
            backend=CacheBackend.MEMORY,
            max_size=3,
            default_ttl=3600.0
        )

    @pytest.fixture
    def cache_backend(self, config):
        return MemoryCacheBackend(config)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache_backend):
        """設定と取得のテスト"""
        # 設定
        success = await cache_backend.set("test_key", "test_value")
        assert success

        # 取得
        value = await cache_backend.get("test_key")
        assert value == "test_value"

        # 存在しないキー
        none_value = await cache_backend.get("nonexistent_key")
        assert none_value is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache_backend):
        """TTL期限切れのテスト"""
        # 短いTTLで設定
        await cache_backend.set("short_ttl_key", "short_ttl_value", ttl=0.1)

        # すぐに取得（成功）
        value = await cache_backend.get("short_ttl_key")
        assert value == "short_ttl_value"

        # TTL経過後に取得（失敗）
        await asyncio.sleep(0.2)
        expired_value = await cache_backend.get("short_ttl_key")
        assert expired_value is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache_backend):
        """LRU evictionのテスト"""
        # 最大サイズ分設定
        await cache_backend.set("key1", "value1")
        await cache_backend.set("key2", "value2")
        await cache_backend.set("key3", "value3")

        # 全て取得可能
        assert await cache_backend.get("key1") == "value1"
        assert await cache_backend.get("key2") == "value2"
        assert await cache_backend.get("key3") == "value3"

        # key1にアクセス（LRU順序更新）
        await cache_backend.get("key1")

        # 新しいキーを追加（key2がevictされるはず）
        await cache_backend.set("key4", "value4")

        # key2はevictされている
        assert await cache_backend.get("key2") is None
        # 他のキーは残っている
        assert await cache_backend.get("key1") == "value1"
        assert await cache_backend.get("key3") == "value3"
        assert await cache_backend.get("key4") == "value4"

    @pytest.mark.asyncio
    async def test_delete(self, cache_backend):
        """削除のテスト"""
        await cache_backend.set("delete_key", "delete_value")

        # 削除前は存在
        assert await cache_backend.exists("delete_key")

        # 削除
        success = await cache_backend.delete("delete_key")
        assert success

        # 削除後は存在しない
        assert not await cache_backend.exists("delete_key")

        # 存在しないキーの削除
        no_delete = await cache_backend.delete("nonexistent_key")
        assert not no_delete

    @pytest.mark.asyncio
    async def test_clear(self, cache_backend):
        """全削除のテスト"""
        # 複数設定
        await cache_backend.set("key1", "value1")
        await cache_backend.set("key2", "value2")

        # クリア
        success = await cache_backend.clear()
        assert success

        # 全て削除されている
        assert await cache_backend.get("key1") is None
        assert await cache_backend.get("key2") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache_backend):
        """期限切れクリーンアップのテスト"""
        # 期限切れと有効なエントリを設定
        await cache_backend.set("expired", "expired_value", ttl=0.1)
        await cache_backend.set("valid", "valid_value", ttl=3600.0)

        # 期限切れまで待機
        await asyncio.sleep(0.2)

        # クリーンアップ実行
        await cache_backend.cleanup_expired()

        # 期限切れは削除、有効なものは残る
        assert await cache_backend.get("expired") is None
        assert await cache_backend.get("valid") == "valid_value"

    @pytest.mark.asyncio
    async def test_stats(self, cache_backend):
        """統計情報のテスト"""
        # 初期統計
        stats = await cache_backend.get_stats()
        assert stats["backend"] == "memory"
        assert stats["size"] == 0
        assert stats["hit_rate"] == 0.0

        # データ追加とアクセス
        await cache_backend.set("test_key", "test_value")
        await cache_backend.get("test_key")  # hit
        await cache_backend.get("nonexistent")  # miss

        # 統計更新確認
        updated_stats = await cache_backend.get_stats()
        assert updated_stats["size"] == 1
        assert updated_stats["total_hits"] == 1
        assert updated_stats["total_misses"] == 1
        assert updated_stats["hit_rate"] == 0.5


class TestFileCacheBackend:
    """FileCacheBackendクラスのテスト"""

    @pytest.fixture
    def temp_dir(self):
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def config(self, temp_dir):
        return CacheConfig(
            backend=CacheBackend.FILE,
            file_cache_dir=temp_dir,
            default_ttl=3600.0
        )

    @pytest.fixture
    def file_cache_backend(self, config):
        return FileCacheBackend(config)

    @pytest.mark.asyncio
    async def test_file_set_and_get(self, file_cache_backend):
        """ファイルキャッシュの設定と取得テスト"""
        # 設定
        success = await file_cache_backend.set("file_key", "file_value")
        assert success

        # 取得
        value = await file_cache_backend.get("file_key")
        assert value == "file_value"

        # ファイルが作成されていることを確認
        cache_dir = Path(file_cache_backend.config.file_cache_dir)
        cache_files = list(cache_dir.glob("*.cache"))
        assert len(cache_files) == 1

    @pytest.mark.asyncio
    async def test_file_ttl_expiration(self, file_cache_backend):
        """ファイルキャッシュのTTL期限切れテスト"""
        # 短いTTLで設定
        await file_cache_backend.set("file_ttl_key", "file_ttl_value", ttl=0.1)

        # すぐに取得（成功）
        value = await file_cache_backend.get("file_ttl_key")
        assert value == "file_ttl_value"

        # TTL経過後に取得（失敗）
        await asyncio.sleep(0.2)
        expired_value = await file_cache_backend.get("file_ttl_key")
        assert expired_value is None

    @pytest.mark.asyncio
    async def test_file_delete(self, file_cache_backend):
        """ファイルキャッシュの削除テスト"""
        await file_cache_backend.set("file_delete_key", "file_delete_value")

        # 削除前は存在
        assert await file_cache_backend.exists("file_delete_key")

        # 削除
        success = await file_cache_backend.delete("file_delete_key")
        assert success

        # 削除後は存在しない
        assert not await file_cache_backend.exists("file_delete_key")

    @pytest.mark.asyncio
    async def test_file_cleanup_expired(self, file_cache_backend):
        """ファイルキャッシュの期限切れクリーンアップテスト"""
        # 期限切れと有効なエントリを設定
        await file_cache_backend.set("file_expired", "file_expired_value", ttl=0.1)
        await file_cache_backend.set("file_valid", "file_valid_value", ttl=3600.0)

        # 期限切れまで待機
        await asyncio.sleep(0.2)

        # クリーンアップ実行
        await file_cache_backend.cleanup_expired()

        # 期限切れは削除、有効なものは残る
        assert await file_cache_backend.get("file_expired") is None
        assert await file_cache_backend.get("file_valid") == "file_valid_value"


class TestRateLimiter:
    """RateLimiterクラスのテスト"""

    @pytest.fixture
    def config(self):
        return RateLimitConfig(
            enabled=True,
            default_limit=5,
            default_window=60.0
        )

    @pytest.fixture
    def rate_limiter(self, config):
        return RateLimiter(config)

    @pytest.mark.asyncio
    async def test_rate_limit_allow(self, rate_limiter):
        """レート制限許可のテスト"""
        # 制限内のリクエスト
        for i in range(5):
            allowed, info = await rate_limiter.check_rate_limit("test_user")
            assert allowed
            assert info.requests == i + 1
            assert info.limit == 5

    @pytest.mark.asyncio
    async def test_rate_limit_exceed(self, rate_limiter):
        """レート制限超過のテスト"""
        # 制限まで使い切る
        for i in range(5):
            allowed, info = await rate_limiter.check_rate_limit("test_user")
            assert allowed

        # 制限超過
        blocked, info = await rate_limiter.check_rate_limit("test_user")
        assert not blocked
        assert info.is_exceeded
        assert info.requests == 5

    @pytest.mark.asyncio
    async def test_rate_limit_window_reset(self, rate_limiter):
        """レート制限ウィンドウリセットのテスト"""
        # 制限まで使い切る
        for i in range(5):
            await rate_limiter.check_rate_limit("test_user")

        # 制限超過確認
        blocked, info = await rate_limiter.check_rate_limit("test_user")
        assert not blocked

        # ウィンドウを手動でリセット
        await rate_limiter.reset_rate_limit("test_user")

        # リセット後は再び許可
        allowed, info = await rate_limiter.check_rate_limit("test_user")
        assert allowed
        assert info.requests == 1

    @pytest.mark.asyncio
    async def test_rate_limit_different_users(self, rate_limiter):
        """異なるユーザーのレート制限テスト"""
        # ユーザー1が制限まで使用
        for i in range(5):
            await rate_limiter.check_rate_limit("user1")

        blocked1, _ = await rate_limiter.check_rate_limit("user1")
        assert not blocked1

        # ユーザー2は影響を受けない
        allowed2, _ = await rate_limiter.check_rate_limit("user2")
        assert allowed2

    @pytest.mark.asyncio
    async def test_get_remaining(self, rate_limiter):
        """残りリクエスト数取得のテスト"""
        # 初期状態
        remaining = await rate_limiter.get_remaining("test_user")
        assert remaining == 5

        # 2回使用後
        await rate_limiter.check_rate_limit("test_user")
        await rate_limiter.check_rate_limit("test_user")

        remaining = await rate_limiter.get_remaining("test_user")
        assert remaining == 3

    @pytest.mark.asyncio
    async def test_rate_limit_disabled(self):
        """レート制限無効時のテスト"""
        config = RateLimitConfig(enabled=False)
        rate_limiter = RateLimiter(config)

        # 無効時は常に許可
        for i in range(100):  # 制限を大幅に超える
            allowed, info = await rate_limiter.check_rate_limit("test_user")
            assert allowed


class TestCacheManager:
    """CacheManagerクラスのテスト"""

    @pytest.fixture
    def cache_config(self):
        return CacheConfig(
            enabled=True,
            backend=CacheBackend.MEMORY,
            cache_key_fields=["provider", "model", "messages"]
        )

    @pytest.fixture
    def rate_limit_config(self):
        return RateLimitConfig(
            enabled=True,
            default_limit=10,
            default_window=60.0
        )

    @pytest.fixture
    def cache_manager(self, cache_config, rate_limit_config):
        return CacheManager(cache_config, rate_limit_config)

    def test_cache_manager_initialization(self, cache_manager):
        """CacheManagerの初期化テスト"""
        assert cache_manager.cache_config.enabled
        assert cache_manager.rate_limit_config.enabled
        assert cache_manager.backend is not None
        assert cache_manager.rate_limiter is not None

    def test_generate_cache_key(self, cache_manager):
        """キャッシュキー生成のテスト"""
        # 基本的なキー生成
        key1 = cache_manager.generate_cache_key(
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )

        # 同じデータからは同じキー
        key2 = cache_manager.generate_cache_key(
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert key1 == key2

        # 異なるデータからは異なるキー
        key3 = cache_manager.generate_cache_key(
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hi"}]
        )
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_cache_response_and_get(self, cache_manager):
        """レスポンスキャッシュと取得のテスト"""
        response_data = TestDataFactory.create_chat_response()
        request_params = {
            "provider": "azure",
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}]
        }

        # キャッシュ
        success = await cache_manager.cache_response(response_data, **request_params)
        assert success

        # 取得
        cached_response = await cache_manager.get_cached_response(**request_params)
        assert cached_response == response_data

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """キャッシュ無効時のテスト"""
        cache_config = CacheConfig(enabled=False)
        rate_limit_config = RateLimitConfig()
        cache_manager = CacheManager(cache_config, rate_limit_config)

        response_data = TestDataFactory.create_chat_response()

        # キャッシュ無効時は保存されない
        success = await cache_manager.cache_response(
            response_data,
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert not success

        # 取得もNone
        cached_response = await cache_manager.get_cached_response(
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert cached_response is None

    @pytest.mark.asyncio
    async def test_cache_streaming_skip(self, cache_manager):
        """ストリーミングレスポンスのキャッシュスキップテスト"""
        # ストリーミングキャッシュが無効の場合
        cache_manager.cache_config.cache_streaming = False

        response_data = TestDataFactory.create_chat_response()

        # ストリーミングリクエストはキャッシュされない
        success = await cache_manager.cache_response(
            response_data,
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True
        )
        assert not success

    @pytest.mark.asyncio
    async def test_rate_limit_check(self, cache_manager):
        """レート制限チェックのテスト"""
        # 通常のレート制限チェック
        allowed, info = await cache_manager.check_rate_limit("test_user")
        assert allowed
        assert info.limit == 10

        # プロバイダー別制限
        cache_manager.rate_limit_config.provider_limits["azure"] = {
            "limit": 5,
            "window": 30.0
        }

        allowed, info = await cache_manager.check_rate_limit("test_user_2", "provider:azure")
        assert allowed
        assert info.limit == 5

    @pytest.mark.asyncio
    async def test_cleanup_tasks(self, cache_manager):
        """クリーンアップタスクのテスト"""
        # タスク開始
        await cache_manager.start_cleanup_task()
        assert cache_manager._cleanup_task is not None

        # 少し待機
        await asyncio.sleep(0.1)

        # タスク停止
        await cache_manager.stop_cleanup_task()
        assert cache_manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_manager):
        """キャッシュ統計のテスト"""
        # データ追加
        await cache_manager.cache_response(
            TestDataFactory.create_chat_response(),
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )

        # 統計取得
        stats = await cache_manager.get_cache_stats()

        assert "cache" in stats
        assert "rate_limiter" in stats
        assert "config" in stats
        assert stats["config"]["cache_enabled"]
        assert stats["config"]["backend"] == "memory"

    @pytest.mark.asyncio
    async def test_clear_cache(self, cache_manager):
        """キャッシュクリアのテスト"""
        # データ追加
        await cache_manager.cache_response(
            TestDataFactory.create_chat_response(),
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )

        # クリア前は取得可能
        cached = await cache_manager.get_cached_response(
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert cached is not None

        # クリア
        success = await cache_manager.clear_cache()
        assert success

        # クリア後は取得不可
        cleared = await cache_manager.get_cached_response(
            provider="azure",
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
        assert cleared is None


@pytest.mark.asyncio
class TestCachingIntegration:
    """キャッシングシステムの統合テスト"""

    async def test_full_caching_workflow(self):
        """完全なキャッシングワークフローのテスト"""
        cache_config = CacheConfig(
            enabled=True,
            backend=CacheBackend.MEMORY,
            cleanup_interval=0.1
        )

        rate_limit_config = RateLimitConfig(
            enabled=True,
            default_limit=5,
            default_window=60.0
        )

        cache_manager = CacheManager(cache_config, rate_limit_config)

        try:
            # クリーンアップタスク開始
            await cache_manager.start_cleanup_task()

            # テストデータ
            request_params = {
                "provider": "azure",
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello, world!"}]
            }
            response_data = TestDataFactory.create_chat_response("Hi there!")

            # レート制限チェック（許可）
            allowed, rate_info = await cache_manager.check_rate_limit("user123")
            assert allowed
            assert rate_info.requests == 1

            # レスポンスキャッシュ
            success = await cache_manager.cache_response(response_data, **request_params)
            assert success

            # キャッシュからレスポンス取得
            cached_response = await cache_manager.get_cached_response(**request_params)
            assert cached_response == response_data

            # 統計確認
            stats = await cache_manager.get_cache_stats()
            assert stats["cache"]["size"] == 1
            assert stats["rate_limiter"]["active_windows"] == 1

            # レート制限まで使用
            for i in range(4):  # 残り4回（最初に1回使用済み）
                allowed, _ = await cache_manager.check_rate_limit("user123")
                assert allowed

            # 制限超過
            blocked, rate_info = await cache_manager.check_rate_limit("user123")
            assert not blocked
            assert rate_info.is_exceeded

            # 異なるユーザーは影響なし
            allowed_other, _ = await cache_manager.check_rate_limit("user456")
            assert allowed_other

        finally:
            await cache_manager.stop_cleanup_task()

    async def test_cache_key_consistency(self):
        """キャッシュキーの一貫性テスト"""
        cache_config = CacheConfig(
            cache_key_fields=["provider", "model", "messages", "temperature"]
        )
        rate_limit_config = RateLimitConfig()
        cache_manager = CacheManager(cache_config, rate_limit_config)

        # 同じパラメータからは同じキー
        params1 = {
            "provider": "azure",
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "max_tokens": 100  # cache_key_fieldsに含まれない
        }

        params2 = {
            "provider": "azure",
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "temperature": 0.7,
            "max_tokens": 200  # 異なる値だがキーには影響しない
        }

        key1 = cache_manager.generate_cache_key(**params1)
        key2 = cache_manager.generate_cache_key(**params2)
        assert key1 == key2

        # temperatureが異なれば異なるキー
        params3 = {**params1, "temperature": 0.8}
        key3 = cache_manager.generate_cache_key(**params3)
        assert key1 != key3
