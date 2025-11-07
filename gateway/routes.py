"""OpenAI-compatible endpoint routing

OpenAI API 互換のエンドポイントを提供する FastAPI アプリケーション。
クライアントは標準的な OpenAI ライブラリで接続可能。

Why: FastAPI の `on_event` は非推奨のため、アプリのライフサイクル管理は
lifespan ハンドラに移行する（2025 互換性対応）。
"""

import logging
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from gateway import azure_proxy

# ロギング設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

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
            "input": error.get("input")
        }

        # A5M2互換性: modelフィールドが欠けている場合の特別なヘルプメッセージ
        if error["type"] == "missing" and "model" in error["loc"]:
            error_detail["help"] = "A5M2 users: Make sure to include the 'model' field in your request. Example: {'model': 'gpt-4', ...}"

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
                "streaming": "Set 'stream': false or omit it (streaming not supported)"
            }
        }
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


# === エンドポイント ===


@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "service": "YuiGateway",
        "version": "0.1.0",
        "description": "Entra ID-based local proxy to Azure OpenAI",
        "endpoints": ["/v1/chat/completions"],
    }


@app.get("/health")
async def health():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> dict[str, Any]:
    """チャット補完エンドポイント（OpenAI 互換）

    OpenAI API の /v1/chat/completions と同じインターフェースを提供。
    リクエストは Entra ID トークン認証を経て Azure OpenAI に転送される。

    Args:
        request: チャット補完リクエスト

    Returns:
        Dict[str, Any]: Azure OpenAI からのレスポンス

    Raises:
        HTTPException: プロキシ処理に失敗した場合
    """
    # A5M2 デバッグのための詳細ログ
    logger.info(f"=== Chat Completion Request ===")
    logger.info(f"Model: {request.model}")
    logger.info(f"Messages count: {len(request.messages)}")
    logger.info(f"Temperature: {request.temperature}")
    logger.info(f"Max tokens: {request.max_tokens}")
    logger.info(f"Stream: {request.stream}")

    # ストリーミングリクエストのチェック
    if request.stream:
        logger.warning("Streaming request detected but not supported")
        raise HTTPException(
            status_code=501,
            detail={
                "error": "streaming_not_supported",
                "message": "Streaming responses are not currently supported",
                "help": "Please set 'stream': false or omit the stream parameter"
            }
        )

    # メッセージ内容をログ（デバッグレベル）
    for i, msg in enumerate(request.messages):
        logger.debug(f"Message {i}: {msg.role} - {msg.content[:100]}...")

    try:
        # リクエストを辞書に変換
        request_dict = request.model_dump(exclude_none=True)

        # Azure OpenAI にプロキシ
        response = await azure_proxy.get_proxy().chat_completion(request_dict)

        # レスポンス情報をログ
        logger.info(f"Response received - Model: {response.get('model', 'unknown')}")
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
            available_models = list(settings.model_mapping.keys())
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "deployment_not_found",
                    "message": f"The specified model deployment was not found",
                    "requested_model": request.model,
                    "available_models": available_models,
                    "help": "Use one of the available model names or check your Azure OpenAI deployment"
                }
            ) from e

        raise HTTPException(
            status_code=500, detail=f"Failed to process request: {str(e)}"
        ) from e


async def shutdown_event():
    """Backward-compatible shutdown hook for tests.

    Why: 既存のユニットテストが `shutdown_event` を直接呼ぶため、
    lifespan 置換後も互換APIとして残す。
    """
    proxy = azure_proxy.get_proxy()
    await proxy.close()

# 旧 on_event("shutdown") は lifespan に置換済み
