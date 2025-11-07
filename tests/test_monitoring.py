"""Test cases for monitoring system

モニタリングシステムの包括的テスト。
メトリクス収集、アラート、ヘルスチェック機能をテスト。
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

from gateway.monitoring import (
    MonitoringConfig, MetricsCollector, AlertManager, MonitoringManager,
    RequestMetrics, ProviderHealth, AlertLevel
)
from tests.test_utils import TestDataFactory


class TestRequestMetrics:
    """RequestMetricsクラスのテスト"""

    def test_request_metrics_creation(self):
        """RequestMetricsの作成をテスト"""
        metrics = RequestMetrics(
            provider="azure",
            model="gpt-4",
            request_id="test-123",
            start_time=time.time()
        )

        assert metrics.provider == "azure"
        assert metrics.model == "gpt-4"
        assert metrics.request_id == "test-123"
        assert metrics.end_time is None
        assert metrics.status_code is None
        assert not metrics.stream

    def test_request_metrics_duration_calculation(self):
        """期間計算のテスト"""
        start_time = time.time()
        metrics = RequestMetrics(
            provider="azure",
            model="gpt-4",
            request_id="test-123",
            start_time=start_time
        )

        # 完了前は None
        assert metrics.duration is None

        # 完了後は期間を計算
        metrics.end_time = start_time + 1.5
        assert abs(metrics.duration - 1.5) < 0.001

    def test_request_metrics_success_property(self):
        """成功判定のテスト"""
        metrics = RequestMetrics(
            provider="azure",
            model="gpt-4",
            request_id="test-123",
            start_time=time.time()
        )

        # ステータスコードなしは失敗
        assert not metrics.success

        # 2xx系は成功
        metrics.status_code = 200
        assert metrics.success

        metrics.status_code = 201
        assert metrics.success

        # その他は失敗
        metrics.status_code = 400
        assert not metrics.success

        metrics.status_code = 500
        assert not metrics.success


class TestMetricsCollector:
    """MetricsCollectorクラスのテスト"""

    @pytest.fixture
    def config(self):
        return MonitoringConfig(
            enabled=True,
            providers=["azure", "openai"]
        )

    @pytest.fixture
    def collector(self, config):
        return MetricsCollector(config)

    def test_metrics_collector_initialization(self, collector):
        """MetricsCollectorの初期化をテスト"""
        assert collector.config.enabled
        assert len(collector.request_history) == 0
        assert collector.registry is not None

    def test_record_request_lifecycle(self, collector):
        """リクエストライフサイクルの記録をテスト"""
        # リクエスト開始
        metrics = collector.record_request_start(
            provider="azure",
            model="gpt-4",
            request_id="test-123"
        )

        assert metrics.provider == "azure"
        assert metrics.model == "gpt-4"
        assert metrics.request_id == "test-123"
        assert metrics.start_time > 0

        # リクエスト完了
        collector.record_request_end(
            metrics=metrics,
            status_code=200,
            tokens_used=15
        )

        assert metrics.status_code == 200
        assert metrics.tokens_used == 15
        assert metrics.end_time is not None
        assert len(collector.request_history) == 1

    def test_get_provider_stats(self, collector):
        """プロバイダー統計の取得をテスト"""
        # テストデータ作成
        start_time = time.time()

        # 成功リクエスト
        for i in range(3):
            metrics = RequestMetrics(
                provider="azure",
                model="gpt-4",
                request_id=f"success-{i}",
                start_time=start_time,
                end_time=start_time + 1.0,
                status_code=200,
                tokens_used=10
            )
            collector.request_history.append(metrics)

        # 失敗リクエスト
        for i in range(2):
            metrics = RequestMetrics(
                provider="azure",
                model="gpt-4",
                request_id=f"error-{i}",
                start_time=start_time,
                end_time=start_time + 2.0,
                status_code=500
            )
            collector.request_history.append(metrics)

        # 統計取得
        stats = collector.get_provider_stats("azure", time_window=3600)

        assert stats["provider"] == "azure"
        assert stats["total_requests"] == 5
        assert stats["successful_requests"] == 3
        assert stats["failed_requests"] == 2
        assert abs(stats["success_rate"] - 0.6) < 0.001
        assert abs(stats["error_rate"] - 0.4) < 0.001
        assert stats["total_tokens"] == 30

    def test_get_provider_stats_empty(self, collector):
        """空の統計取得をテスト"""
        stats = collector.get_provider_stats("nonexistent")

        assert stats["provider"] == "nonexistent"
        assert stats["total_requests"] == 0
        assert stats["success_rate"] == 0.0
        assert stats["error_rate"] == 0.0

    def test_update_provider_health(self, collector):
        """プロバイダーヘルス更新をテスト"""
        collector.update_provider_health("azure", healthy=True, response_time=1.5)

        # Prometheusメトリクスが正しく設定されることを確認
        # 実際の値の検証は統合テストで行う
        assert True  # メソッドが例外なく実行されることを確認


class TestAlertManager:
    """AlertManagerクラスのテスト"""

    @pytest.fixture
    def config(self):
        return MonitoringConfig(
            alert_thresholds={
                "error_rate": 0.1,  # 10%
                "response_time_p95": 2.0,  # 2 seconds
                "availability": 0.9  # 90%
            }
        )

    @pytest.fixture
    def alert_manager(self, config):
        return AlertManager(config)

    def test_alert_manager_initialization(self, alert_manager):
        """AlertManagerの初期化をテスト"""
        assert len(alert_manager.alert_handlers) == 0
        assert len(alert_manager.active_alerts) == 0

    def test_add_alert_handler(self, alert_manager):
        """アラートハンドラーの追加をテスト"""
        def test_handler(level, message, data):
            pass

        alert_manager.add_alert_handler(test_handler)
        assert len(alert_manager.alert_handlers) == 1

    def test_check_alerts_error_rate(self, alert_manager):
        """エラー率アラートのテスト"""
        alert_triggered = False

        def test_handler(level, message, data):
            nonlocal alert_triggered
            alert_triggered = True
            assert level == AlertLevel.ERROR
            assert "error rate" in message.lower()
            assert data["provider"] == "azure"
            assert data["error_rate"] == 0.15

        alert_manager.add_alert_handler(test_handler)

        stats = {
            "provider": "azure",
            "error_rate": 0.15,  # 閾値(0.1)を超過
            "avg_response_time": 1.0,
            "success_rate": 0.85
        }

        alert_manager.check_alerts(stats)
        assert alert_triggered

    def test_check_alerts_response_time(self, alert_manager):
        """レスポンス時間アラートのテスト"""
        alert_triggered = False

        def test_handler(level, message, data):
            nonlocal alert_triggered
            alert_triggered = True
            assert level == AlertLevel.WARNING
            assert "response time" in message.lower()

        alert_manager.add_alert_handler(test_handler)

        stats = {
            "provider": "azure",
            "error_rate": 0.05,
            "avg_response_time": 3.0,  # 閾値(2.0)を超過
            "success_rate": 0.95
        }

        alert_manager.check_alerts(stats)
        assert alert_triggered

    def test_check_alerts_availability(self, alert_manager):
        """可用性アラートのテスト"""
        alert_triggered = False

        def test_handler(level, message, data):
            nonlocal alert_triggered
            alert_triggered = True
            assert level == AlertLevel.CRITICAL
            assert "availability" in message.lower()

        alert_manager.add_alert_handler(test_handler)

        stats = {
            "provider": "azure",
            "error_rate": 0.2,
            "avg_response_time": 1.0,
            "success_rate": 0.8  # 閾値(0.9)を下回る
        }

        alert_manager.check_alerts(stats)
        assert alert_triggered

    def test_alert_suppression(self, alert_manager):
        """アラート抑制のテスト"""
        alert_count = 0

        def test_handler(level, message, data):
            nonlocal alert_count
            alert_count += 1

        alert_manager.add_alert_handler(test_handler)

        stats = {
            "provider": "azure",
            "error_rate": 0.15,  # エラー率アラートのみトリガー
            "avg_response_time": 1.0,
            "success_rate": 0.95  # 可用性アラートはトリガーしない
        }

        # 最初のアラート
        alert_manager.check_alerts(stats)
        assert alert_count == 1

        # 同じアラートは抑制される（5分間）
        alert_manager.check_alerts(stats)
        assert alert_count == 1  # 増加しない


class TestMonitoringManager:
    """MonitoringManagerクラスのテスト"""

    @pytest.fixture
    def config(self):
        return MonitoringConfig(
            enabled=True,
            providers=["azure"],
            export_interval=1  # テスト用に短く設定
        )

    @pytest.fixture
    def monitoring_manager(self, config):
        return MonitoringManager(config)

    def test_monitoring_manager_initialization(self, monitoring_manager):
        """MonitoringManagerの初期化をテスト"""
        assert monitoring_manager.config.enabled
        assert monitoring_manager.metrics is not None
        assert monitoring_manager.alerts is not None
        assert monitoring_manager._monitoring_task is None

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, monitoring_manager):
        """モニタリング開始・停止のテスト"""
        # 開始
        await monitoring_manager.start_monitoring()
        assert monitoring_manager._monitoring_task is not None

        # 少し待機してループが実行されることを確認
        await asyncio.sleep(0.1)

        # 停止
        await monitoring_manager.stop_monitoring()
        assert monitoring_manager._monitoring_task is None

    @pytest.mark.asyncio
    async def test_monitoring_disabled(self):
        """モニタリング無効時のテスト"""
        config = MonitoringConfig(enabled=False)
        manager = MonitoringManager(config)

        await manager.start_monitoring()
        assert manager._monitoring_task is None

    def test_default_alert_handler(self, monitoring_manager):
        """デフォルトアラートハンドラーのテスト"""
        # デフォルトハンドラーが追加されていることを確認
        assert len(monitoring_manager.alerts.alert_handlers) == 1

        # ハンドラーが例外なく実行されることを確認
        handler = monitoring_manager.alerts.alert_handlers[0]

        try:
            handler(AlertLevel.INFO, "Test message", {"test": "data"})
        except Exception as e:
            pytest.fail(f"Default alert handler raised exception: {e}")


class TestMonitoringIntegration:
    """モニタリングシステムの統合テスト"""

    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(self):
        """完全なモニタリングワークフローのテスト"""
        config = MonitoringConfig(
            enabled=True,
            providers=["azure"],
            export_interval=0.1,  # 高速テスト用
            alert_thresholds={"error_rate": 0.5}
        )

        manager = MonitoringManager(config)

        # アラートハンドラー設定
        alerts_received = []

        def capture_alerts(level, message, data):
            alerts_received.append((level, message, data))

        manager.alerts.add_alert_handler(capture_alerts)

        # モニタリング開始
        await manager.start_monitoring()

        try:
            # テストリクエスト記録
            metrics = manager.metrics.record_request_start("azure", "gpt-4", "test-1")
            manager.metrics.record_request_end(metrics, 200, 10)

            # エラーリクエスト記録（アラートトリガー用）
            for i in range(3):
                error_metrics = manager.metrics.record_request_start("azure", "gpt-4", f"error-{i}")
                manager.metrics.record_request_end(error_metrics, 500)

            # モニタリングループが実行されるまで待機
            await asyncio.sleep(0.2)

            # 統計確認
            stats = manager.metrics.get_provider_stats("azure")
            assert stats["total_requests"] == 4
            assert stats["error_rate"] == 0.75  # 3/4

            # アラート確認（エラー率が0.5を超過）
            assert len(alerts_received) > 0

            # ヘルス情報確認
            health_summary = manager.metrics.get_health_summary()
            assert "providers" in health_summary
            assert "azure" in health_summary["providers"]

        finally:
            await manager.stop_monitoring()

    @patch('gateway.monitoring.generate_latest')
    def test_metrics_export(self, mock_generate_latest):
        """メトリクスエクスポートのテスト"""
        mock_generate_latest.return_value = b"# HELP test_metric Test metric\ntest_metric 1.0\n"

        config = MonitoringConfig()
        collector = MetricsCollector(config)

        exported = collector.export_metrics()
        assert "test_metric" in exported
        mock_generate_latest.assert_called_once_with(collector.registry)
