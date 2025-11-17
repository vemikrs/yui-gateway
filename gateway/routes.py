"""OpenAI-compatible endpoint routing

OpenAI API 互換のエンドポイントを提供する FastAPI アプリケーション。
クライアントは標準的な OpenAI ライブラリで接続可能。

Why: FastAPI の `on_event` は非推奨のため、アプリのライフサイクル管理は
lifespan ハンドラに移行する（2025 互換性対応）。
"""

import logging
import re
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, ValidationError, field_validator
import json
import uuid
from datetime import datetime

from gateway import azure_proxy
from gateway.caching import cache_manager


# ログサニタイゼーション用フィルタ
class SensitiveDataFilter(logging.Filter):
    """機密情報をマスクするログフィルタ"""

    SENSITIVE_PATTERNS = [
        (
            re.compile(r"Bearer [A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
            "Bearer [REDACTED]",
        ),
        (
            re.compile(r'"api[_-]?key"\s*:\s*"[^"]+"', re.IGNORECASE),
            '"api_key": "[REDACTED]"',
        ),
        (
            re.compile(r'"client[_-]?secret"\s*:\s*"[^"]+"', re.IGNORECASE),
            '"client_secret": "[REDACTED]"',
        ),
        (
            re.compile(r'"password"\s*:\s*"[^"]+"', re.IGNORECASE),
            '"password": "[REDACTED]"',
        ),
        (re.compile(r'"token"\s*:\s*"[^"]+"', re.IGNORECASE), '"token": "[REDACTED]"'),
    ]

    def filter(self, record):
        message = record.getMessage()
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            message = pattern.sub(replacement, message)
        record.msg = message
        record.args = ()
        return True


# ロギング設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.addFilter(SensitiveDataFilter())

# セキュリティ: API認証（オプション、環境変数で有効化）
import os
from gateway.settings import SettingsManager

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(api_key: str = Depends(api_key_header)):
    """API キー認証（設定されている場合のみ）

    Why: グローバル変数ではなく SettingsManager.get_settings() から取得することで、
    テスト時に環境変数を変更→SettingsManager.reset→検証が可能になる。
    モジュールリロードに依存しない安定したテスト設計。
    """
    # Settings から API キーを取得（実行時評価）
    current_settings = SettingsManager.get_settings()
    configured_key = current_settings.yuigateway_api_key

    if configured_key is None:
        # API_KEYが未設定の場合は認証をスキップ（開発モード）
        return None
    if api_key is None or api_key != configured_key:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App lifespan handler for startup/shutdown cleanup.

    Why: `on_event` は非推奨のため、終了時のクリーンアップをここで実施する。
    起動時は特別な初期化を行っていないため、yield 前は何もしない。
    """
    # Startup phase
    yield
    # Shutdown phase
    logger.info("Shutting down YuiGateway")
    inst = getattr(azure_proxy, "_proxy_instance", None)
    if inst is not None:
        await inst.close()


# FastAPI アプリケーション（lifespan 対応）
app = FastAPI(
    title="YuiGateway",
    description="Entra ID-based local proxy to Azure OpenAI",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic バリデーションエラーをより詳細に報告

    A5M2 などのクライアントでのデバッグを容易にするため、
    エラーの詳細情報を構造化して返す。
    """
    logger.error(f"Validation error for {request.method} {request.url}: {exc}")

    errors = []
    for error in exc.errors():
        error_detail = {
            "field": " -> ".join(str(loc) for loc in error["loc"][1:]),  # "body" を除去
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input"),
        }

        # A5M2互換性: modelフィールドが欠けている場合の特別なヘルプメッセージ
        if error["type"] == "missing" and "model" in error["loc"]:
            error_detail["help"] = (
                "A5M2 users: Make sure to include the 'model' field in your request. Example: {'model': 'gpt-4', ...}"
            )

        errors.append(error_detail)

    return JSONResponse(
        status_code=422,
        content={
            "error": "validation_error",
            "message": "Request validation failed",
            "details": errors,
            "help": "Check that your request matches the OpenAI chat completions API format",
            "common_issues": {
                "missing_model": "A5M2 users should include 'model' field (e.g., 'gpt-4')",
                "streaming": "Streaming is now supported! Use 'stream': true for real-time responses",
            },
        },
    )


# === Pydantic モデル定義 ===


class Message(BaseModel):
    """チャットメッセージ"""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """チャット補完リクエスト（OpenAI 互換）"""

    model: str = "gpt-4"  # A5M2互換性のためデフォルト値を設定
    messages: list[Message]
    temperature: float | None = 1.0
    top_p: float | None = 1.0
    n: int | None = 1
    stream: bool | None = False
    max_tokens: int | None = None
    presence_penalty: float | None = 0.0
    frequency_penalty: float | None = 0.0

    @field_validator("model")
    @classmethod
    def validate_model_name(cls, v: str) -> str:
        """モデル名のバリデーション（セキュリティ: インジェクション防止）"""
        # 許可される文字: 英数字、ハイフン、アンダースコア、ドット
        if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$", v):
            raise ValueError(
                f"Invalid model name format: {v}. "
                "Model names must start with alphanumeric and contain only "
                "alphanumeric, dots, hyphens, or underscores (max 128 chars)."
            )
        return v


# === エンドポイント ===


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "service": "YuiGateway",
        "version": "0.1.0",
        "description": "Entra ID-based local proxy to Azure OpenAI",
        "endpoints": ["/v1/chat/completions"],
        "features": ["streaming", "model_mapping", "enhanced_error_handling"],
        "streaming": "Supported via 'stream': true parameter",
    }


@app.get("/health")
async def health():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    client_request: Request,
    api_key: str = Depends(verify_api_key),
):
    """チャット補完エンドポイント（OpenAI 互換）

    OpenAI API の /v1/chat/completions と同じインターフェースを提供。
    リクエストは Entra ID トークン認証を経て Azure OpenAI に転送される。

    Args:
        request: チャット補完リクエスト
        client_request: FastAPIリクエストオブジェクト
        api_key: API認証キー（設定されている場合）

    Returns:
        Dict[str, Any]: Azure OpenAI からのレスポンス

    Raises:
        HTTPException: プロキシ処理に失敗した場合
    """
    # セキュリティ修正4: レート制限チェック
    client_ip = client_request.client.host if client_request.client else "unknown"
    rate_limit_key = f"ip:{client_ip}"
    allowed, rate_info = await cache_manager.check_rate_limit(rate_limit_key)

    if not allowed:
        logger.warning(f"Rate limit exceeded for {client_ip}")
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Too many requests",
                "retry_after": int(rate_info.reset_time - rate_info.window_start),
            },
        )

    # セキュリティ修正1: 機密情報をログに出力しない（サニタイズ済み）
    logger.info(f"=== Chat Completion Request ===")
    logger.info(f"Model: {request.model}")
    logger.info(f"Messages count: {len(request.messages)}")
    logger.info(f"Temperature: {request.temperature}")
    logger.info(f"Max tokens: {request.max_tokens}")
    logger.info(f"Stream: {request.stream}")
    logger.info(f"Client IP: {client_ip}")

    # メッセージ内容はログに出力しない（セキュリティ修正）

    try:
        # リクエストを辞書に変換
        request_dict = request.model_dump(exclude_none=True)

        if request.stream:
            # ストリーミングレスポンス
            logger.info("Processing streaming request")
            return StreamingResponse(
                stream_chat_completion(request_dict),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        else:
            # 通常のレスポンス
            response = await azure_proxy.get_proxy().chat_completion(request_dict)

            # レスポンス情報をログ
            logger.info(
                f"Response received - Model: {response.get('model', 'unknown')}"
            )
            logger.info(f"Usage: {response.get('usage', {})}")
            logger.info(f"=== Request completed successfully ===")

            return response

    except Exception as e:
        logger.error(f"Error processing chat completion: {str(e)}")

        # Azure OpenAI のエラーレスポンスをより詳細に解析
        error_detail = str(e)
        if "404 DeploymentNotFound" in error_detail:
            # デプロイメント名エラーの場合、利用可能なモデルを提案
            from gateway.settings import settings

            # model_mappingsからモデル名を取得（空の場合はavailable_modelsを使用）
            if settings.model_mappings:
                available_models = [
                    (
                        m.get("source_model")
                        if isinstance(m, dict)
                        else getattr(m, "source_model", None)
                    )
                    for m in settings.model_mappings
                ]
                available_models = [m for m in available_models if m]  # None除外
            else:
                available_models = settings.available_models

            raise HTTPException(
                status_code=404,
                detail={
                    "error": "deployment_not_found",
                    "message": f"The specified model deployment was not found",
                    "requested_model": request.model,
                    "available_models": available_models,
                    "help": "Use one of the available model names or check your Azure OpenAI deployment",
                },
            ) from e

        raise HTTPException(
            status_code=500, detail=f"Failed to process request: {str(e)}"
        ) from e


async def stream_chat_completion(request_dict: dict[str, Any]):
    """ストリーミングチャット補完の処理

    Azure OpenAIのストリーミングレスポンスをOpenAI互換形式で返す。
    Server-Sent Events (SSE) 形式でデータを送信。
    """
    try:
        # ストリーミングレスポンスをAzure OpenAIから取得
        stream_response = azure_proxy.get_proxy().chat_completion_stream(request_dict)

        async for chunk in stream_response:
            if chunk:
                # OpenAI互換のSSE形式で送信
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

        # ストリーム終了のシグナル
        yield "data: [DONE]\n\n"

        logger.info("=== Streaming request completed successfully ===")

    except Exception as e:
        logger.error(f"Error in streaming response: {str(e)}")
        # エラーをSSE形式で送信
        error_chunk = {
            "error": {
                "message": str(e),
                "type": "stream_error",
                "code": "internal_error",
            }
        }
        yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


async def shutdown_event():
    """Backward-compatible shutdown hook for tests.

    Why: 既存のユニットテストが `shutdown_event` を直接呼ぶため、
    lifespan 置換後も互換APIとして残す。
    """
    proxy = azure_proxy.get_proxy()
    await proxy.close()


# 旧 on_event("shutdown") は lifespan に置換済み
