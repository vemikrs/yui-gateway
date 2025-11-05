"""OpenAI-compatible endpoint routing

OpenAI API 互換のエンドポイントを提供する FastAPI アプリケーション。
クライアントは標準的な OpenAI ライブラリで接続可能。

Why: FastAPI の `on_event` は非推奨のため、アプリのライフサイクル管理は
lifespan ハンドラに移行する（2025 互換性対応）。
"""

import logging
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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


# === Pydantic モデル定義 ===


class Message(BaseModel):
    """チャットメッセージ"""

    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """チャット補完リクエスト（OpenAI 互換）"""

    model: str
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
    logger.info(f"Received chat completion request for model: {request.model}")

    try:
        # リクエストを辞書に変換
        request_dict = request.model_dump(exclude_none=True)

        # Azure OpenAI にプロキシ
        response = await azure_proxy.get_proxy().chat_completion(request_dict)

        return response

    except Exception as e:
        logger.error(f"Error processing chat completion: {str(e)}")
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
