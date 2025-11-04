"""OpenAI-compatible endpoint routing

OpenAI API 互換のエンドポイントを提供する FastAPI アプリケーション。
クライアントは標準的な OpenAI ライブラリで接続可能。
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

from gateway.azure_proxy import proxy

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI アプリケーション
app = FastAPI(
    title="YuiGateway",
    description="Entra ID-based local proxy to Azure OpenAI",
    version="0.1.0"
)


# === Pydantic モデル定義 ===

class Message(BaseModel):
    """チャットメッセージ"""
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    """チャット補完リクエスト（OpenAI 互換）"""
    model: str
    messages: List[Message]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0


# === エンドポイント ===

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "service": "YuiGateway",
        "version": "0.1.0",
        "description": "Entra ID-based local proxy to Azure OpenAI",
        "endpoints": ["/v1/chat/completions"]
    }


@app.get("/health")
async def health():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> Dict[str, Any]:
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
        response = await proxy.chat_completion(request_dict)
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing chat completion: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process request: {str(e)}"
        )


@app.on_event("shutdown")
async def shutdown_event():
    """アプリケーション終了時のクリーンアップ"""
    logger.info("Shutting down YuiGateway")
    await proxy.close()
