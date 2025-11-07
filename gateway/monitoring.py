"""Comprehensive monitoring system

プロバイダー別メトリクス、パフォーマンス追跡、アラート機能。
Prometheus互換メトリクス、構造化ログ、ヘルスチェックを提供。
"""

import asyncio
import time
import logging
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import json

from prometheus_client import Counter, Histogram, Gauge, Info, CollectorRegistry, generate_latest
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """メトリクスタイプ"""
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"
    INFO = "info"


class AlertLevel(Enum):
    """アラートレベル"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class RequestMetrics:
    """リクエストメトリクス"""
    provider: str
    model: str
    request_id: str
    start_time: float
    end_time: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    stream: bool = False

    @property
    def duration(self) -> Optional[float]:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def success(self) -> bool:
        return self.status_code is not None and 200 <= self.status_code < 300


@dataclass
class ProviderHealth:
    """プロバイダーヘルス状態"""
    provider: str
    healthy: bool
    last_check: datetime
    response_time: Optional[float] = None
    error_rate: float = 0.0
    success_rate: float = 100.0
    total_requests: int = 0
    failed_requests: int = 0


class MonitoringConfig(BaseModel):
    """モニタリング設定"""
    enabled: bool = True
    metrics_endpoint: str = "/metrics"
    export_interval: float = 60.0  # seconds
    retention_period: int = 3600  # seconds
    alert_thresholds: Dict[str, float] = {
        "error_rate": 0.05,  # 5%
        "response_time_p95": 5.0,  # 5 seconds
        "availability": 0.95  # 95%
    }
    providers: List[str] = []
    enable_detailed_logging: bool = False


class MetricsCollector:
    """メトリクス収集クラス"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.registry = CollectorRegistry()
        self._setup_metrics()
        self.request_history: deque = deque(maxlen=10000)
        self._running = False

    def _setup_metrics(self):
        """Prometheusメトリクスのセットアップ"""

        # リクエスト総数
        self.requests_total = Counter(
            'yuigateway_requests_total',
            'Total number of requests',
            ['provider', 'model', 'status'],
            registry=self.registry
        )

        # レスポンス時間
        self.response_time = Histogram(
            'yuigateway_response_duration_seconds',
            'Response duration in seconds',
            ['provider', 'model'],
            registry=self.registry
        )

        # アクティブリクエスト数
        self.active_requests = Gauge(
            'yuigateway_active_requests',
            'Number of active requests',
            ['provider'],
            registry=self.registry
        )

        # トークン使用量
        self.tokens_used = Counter(
            'yuigateway_tokens_total',
            'Total number of tokens used',
            ['provider', 'model', 'type'],
            registry=self.registry
        )

        # エラー率
        self.error_rate = Gauge(
            'yuigateway_error_rate',
            'Error rate by provider',
            ['provider'],
            registry=self.registry
        )

        # プロバイダーヘルス
        self.provider_health = Gauge(
            'yuigateway_provider_health',
            'Provider health status (1=healthy, 0=unhealthy)',
            ['provider'],
            registry=self.registry
        )

        # システム情報
        self.system_info = Info(
            'yuigateway_info',
            'System information',
            registry=self.registry
        )

        # システム情報の設定
        self.system_info.info({
            'version': '0.2.0',
            'monitoring_enabled': str(self.config.enabled)
        })

    def record_request_start(self, provider: str, model: str, request_id: str, stream: bool = False) -> RequestMetrics:
        """リクエスト開始を記録"""
        metrics = RequestMetrics(
            provider=provider,
            model=model,
            request_id=request_id,
            start_time=time.time(),
            stream=stream
        )

        self.active_requests.labels(provider=provider).inc()
        return metrics

    def record_request_end(self, metrics: RequestMetrics, status_code: int, tokens_used: Optional[int] = None, error: Optional[str] = None):
        """リクエスト完了を記録"""
        metrics.end_time = time.time()
        metrics.status_code = status_code
        metrics.tokens_used = tokens_used
        metrics.error = error

        # メトリクス更新
        status = "success" if metrics.success else "error"
        self.requests_total.labels(
            provider=metrics.provider,
            model=metrics.model,
            status=status
        ).inc()

        if metrics.duration:
            self.response_time.labels(
                provider=metrics.provider,
                model=metrics.model
            ).observe(metrics.duration)

        if tokens_used:
            self.tokens_used.labels(
                provider=metrics.provider,
                model=metrics.model,
                type="total"
            ).inc(tokens_used)

        self.active_requests.labels(provider=metrics.provider).dec()

        # 履歴に追加
        self.request_history.append(metrics)

        # 詳細ログ
        if self.config.enable_detailed_logging:
            self._log_request_details(metrics)

    def _log_request_details(self, metrics: RequestMetrics):
        """リクエスト詳細ログ"""
        log_data = {
            "request_id": metrics.request_id,
            "provider": metrics.provider,
            "model": metrics.model,
            "duration": metrics.duration,
            "status_code": metrics.status_code,
            "success": metrics.success,
            "tokens_used": metrics.tokens_used,
            "stream": metrics.stream,
            "timestamp": datetime.fromtimestamp(metrics.start_time).isoformat()
        }

        if metrics.error:
            log_data["error"] = metrics.error

        if metrics.success:
            logger.info(f"Request completed: {json.dumps(log_data)}")
        else:
            logger.error(f"Request failed: {json.dumps(log_data)}")

    def get_provider_stats(self, provider: str, time_window: int = 3600) -> Dict[str, Any]:
        """プロバイダー統計を取得"""
        cutoff_time = time.time() - time_window
        provider_requests = [
            req for req in self.request_history
            if req.provider == provider and req.start_time >= cutoff_time
        ]

        if not provider_requests:
            return {
                "provider": provider,
                "total_requests": 0,
                "success_rate": 0.0,
                "error_rate": 0.0,
                "avg_response_time": 0.0,
                "total_tokens": 0
            }

        successful = [req for req in provider_requests if req.success]
        failed = [req for req in provider_requests if not req.success]

        # レスポンス時間統計
        durations = [req.duration for req in provider_requests if req.duration is not None]
        avg_response_time = sum(durations) / len(durations) if durations else 0.0

        # トークン統計
        total_tokens = sum(req.tokens_used for req in provider_requests if req.tokens_used)

        return {
            "provider": provider,
            "total_requests": len(provider_requests),
            "successful_requests": len(successful),
            "failed_requests": len(failed),
            "success_rate": len(successful) / len(provider_requests) if provider_requests else 0.0,
            "error_rate": len(failed) / len(provider_requests) if provider_requests else 0.0,
            "avg_response_time": avg_response_time,
            "total_tokens": total_tokens,
            "time_window": time_window
        }

    def update_provider_health(self, provider: str, healthy: bool, response_time: Optional[float] = None):
        """プロバイダーヘルス状態を更新"""
        self.provider_health.labels(provider=provider).set(1 if healthy else 0)

        # エラー率も更新
        stats = self.get_provider_stats(provider, 300)  # 5分間の統計
        self.error_rate.labels(provider=provider).set(stats["error_rate"])

    def export_metrics(self) -> str:
        """Prometheus形式でメトリクスをエクスポート"""
        return generate_latest(self.registry).decode('utf-8')

    def get_health_summary(self) -> Dict[str, Any]:
        """全体的なヘルス情報を取得"""
        summary = {
            "overall_health": True,
            "providers": {},
            "total_requests": len(self.request_history),
            "timestamp": datetime.now().isoformat()
        }

        for provider in self.config.providers:
            stats = self.get_provider_stats(provider)
            provider_health = {
                "healthy": stats["error_rate"] < self.config.alert_thresholds["error_rate"],
                "stats": stats
            }

            if not provider_health["healthy"]:
                summary["overall_health"] = False

            summary["providers"][provider] = provider_health

        return summary


class AlertManager:
    """アラート管理クラス"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.alert_handlers: List[Callable] = []
        self.active_alerts: Dict[str, Dict[str, Any]] = {}

    def add_alert_handler(self, handler: Callable[[AlertLevel, str, Dict[str, Any]], None]):
        """アラートハンドラーを追加"""
        self.alert_handlers.append(handler)

    def check_alerts(self, stats: Dict[str, Any]):
        """アラート条件をチェック"""
        provider = stats["provider"]

        # エラー率チェック
        if stats["error_rate"] > self.config.alert_thresholds["error_rate"]:
            self._trigger_alert(
                AlertLevel.ERROR,
                f"High error rate for provider {provider}",
                {
                    "provider": provider,
                    "error_rate": stats["error_rate"],
                    "threshold": self.config.alert_thresholds["error_rate"]
                }
            )

        # レスポンス時間チェック
        if stats["avg_response_time"] > self.config.alert_thresholds["response_time_p95"]:
            self._trigger_alert(
                AlertLevel.WARNING,
                f"High response time for provider {provider}",
                {
                    "provider": provider,
                    "response_time": stats["avg_response_time"],
                    "threshold": self.config.alert_thresholds["response_time_p95"]
                }
            )

        # 可用性チェック
        if stats["success_rate"] < self.config.alert_thresholds["availability"]:
            self._trigger_alert(
                AlertLevel.CRITICAL,
                f"Low availability for provider {provider}",
                {
                    "provider": provider,
                    "availability": stats["success_rate"],
                    "threshold": self.config.alert_thresholds["availability"]
                }
            )

    def _trigger_alert(self, level: AlertLevel, message: str, data: Dict[str, Any]):
        """アラートをトリガー"""
        alert_key = f"{data.get('provider', 'unknown')}_{level.value}"

        # 重複アラートの抑制（5分間）
        if alert_key in self.active_alerts:
            last_alert = self.active_alerts[alert_key]["timestamp"]
            if time.time() - last_alert < 300:  # 5分間
                return

        self.active_alerts[alert_key] = {
            "level": level.value,
            "message": message,
            "data": data,
            "timestamp": time.time()
        }

        # ハンドラー実行
        for handler in self.alert_handlers:
            try:
                handler(level, message, data)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

        # ログ出力
        log_method = getattr(logger, level.value.lower())
        log_method(f"ALERT: {message} - {json.dumps(data)}")


class MonitoringManager:
    """モニタリングマネージャー"""

    def __init__(self, config: MonitoringConfig):
        self.config = config
        self.metrics = MetricsCollector(config)
        self.alerts = AlertManager(config)
        self._monitoring_task: Optional[asyncio.Task] = None

        # デフォルトアラートハンドラー
        self.alerts.add_alert_handler(self._default_alert_handler)

    def _default_alert_handler(self, level: AlertLevel, message: str, data: Dict[str, Any]):
        """デフォルトアラートハンドラー"""
        logger.warning(f"Alert [{level.value.upper()}]: {message}")

    async def start_monitoring(self):
        """モニタリング開始"""
        if not self.config.enabled:
            logger.info("Monitoring is disabled")
            return

        if self._monitoring_task is None:
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("Monitoring started")

    async def stop_monitoring(self):
        """モニタリング停止"""
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            self._monitoring_task = None
            logger.info("Monitoring stopped")

    async def _monitoring_loop(self):
        """モニタリングループ"""
        while True:
            try:
                await asyncio.sleep(self.config.export_interval)

                # 各プロバイダーの統計とアラートチェック
                for provider in self.config.providers:
                    stats = self.metrics.get_provider_stats(provider)
                    self.alerts.check_alerts(stats)

                # 古いデータのクリーンアップ
                self._cleanup_old_data()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

    def _cleanup_old_data(self):
        """古いデータのクリーンアップ"""
        cutoff_time = time.time() - self.config.retention_period

        # リクエスト履歴のクリーンアップ
        while (self.metrics.request_history and
               self.metrics.request_history[0].start_time < cutoff_time):
            self.metrics.request_history.popleft()

        # アクティブアラートのクリーンアップ
        expired_alerts = [
            key for key, alert in self.alerts.active_alerts.items()
            if time.time() - alert["timestamp"] > 3600  # 1時間
        ]
        for key in expired_alerts:
            del self.alerts.active_alerts[key]


# グローバルモニタリングインスタンス
monitoring_config = MonitoringConfig()
monitoring_manager = MonitoringManager(monitoring_config)
