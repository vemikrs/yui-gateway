"""Test utilities and mocks

テスト用のモック、フィクスチャ、ヘルパー関数。
実際のAPIサービスを使用せずにテストを実行するための仕組み。
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

import pytest
from httpx import Response


class MockTokenCache:
    """MSALトークンキャッシュのモック"""

    def __init__(self):
        self.tokens = {}

    def has_cache_changed_since(self, timestamp):
        return False

    def serialize(self):
        return json.dumps(self.tokens)

    def deserialize(self, cache_data):
        if cache_data:
            self.tokens = json.loads(cache_data)


class MockPublicClientApplication:
    """MSAL PublicClientApplicationのモック"""

    def __init__(self, client_id, authority=None, token_cache=None):
        self.client_id = client_id
        self.authority = authority
        self.token_cache = token_cache or MockTokenCache()
        self._tokens = {}

    def get_accounts(self, username=None):
        """アカウント一覧を返す"""
        if username:
            return [{"username": username}] if username in self._tokens else []
        return list(self._tokens.values())

    def acquire_token_silent(self, scopes, account):
        """サイレントトークン取得（成功パターン）"""
        username = account.get("username", "test@example.com")
        if username in self._tokens:
            return {
                "access_token": f"token_for_{username}",
                "expires_in": 3600,
                "token_type": "Bearer"
            }
        return None

    def acquire_token_interactive(self, scopes, **kwargs):
        """インタラクティブトークン取得"""
        username = kwargs.get("login_hint", "test@example.com")
        token = f"interactive_token_for_{username}"

        self._tokens[username] = {"username": username}

        return {
            "access_token": token,
            "expires_in": 3600,
            "token_type": "Bearer",
            "account": {"username": username}
        }

    def set_mock_token(self, username: str, token: str):
        """テスト用のトークンを設定"""
        self._tokens[username] = {"username": username}


class MockHttpxResponse:
    """httpx.Responseのモック"""

    def __init__(self, json_data: Dict[str, Any], status_code: int = 200, headers: Optional[Dict[str, str]] = None):
        self._json_data = json_data
        self.status_code = status_code
        self.headers = headers or {}
        self.is_success = 200 <= status_code < 300

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if not self.is_success:
            raise Exception(f"HTTP {self.status_code}")

    async def aiter_lines(self):
        """ストリーミングレスポンス用"""
        if "choices" in self._json_data:
            # チャットコンプリーション形式
            for i, choice in enumerate(self._json_data["choices"]):
                chunk = {
                    "id": "chatcmpl-test",
                    "object": "chat.completion.chunk",
                    "created": 1234567890,
                    "model": "gpt-4",
                    "choices": [{
                        "index": i,
                        "delta": choice.get("delta", choice.get("message", {})),
                        "finish_reason": choice.get("finish_reason")
                    }]
                }
                yield f"data: {json.dumps(chunk)}\n\n"

            yield "data: [DONE]\n\n"
        else:
            # 生データ
            for line in str(self._json_data).split('\n'):
                yield line


class MockAzureOpenAIService:
    """Azure OpenAI APIのモック"""

    def __init__(self):
        self.call_history = []
        self.response_queue = []
        self.default_response = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a test response"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }

    def set_response(self, response: Dict[str, Any], status_code: int = 200):
        """次のレスポンスを設定"""
        self.response_queue.append((response, status_code))

    def set_error_response(self, error_message: str, status_code: int = 400):
        """エラーレスポンスを設定"""
        error_response = {
            "error": {
                "message": error_message,
                "type": "invalid_request_error",
                "code": "invalid_request"
            }
        }
        self.response_queue.append((error_response, status_code))

    async def mock_post(self, url: str, **kwargs) -> MockHttpxResponse:
        """POST リクエストのモック"""
        self.call_history.append({
            "url": url,
            "method": "POST",
            "headers": kwargs.get("headers", {}),
            "json": kwargs.get("json", {}),
            "timestamp": datetime.now().isoformat()
        })

        if self.response_queue:
            response_data, status_code = self.response_queue.pop(0)
            return MockHttpxResponse(response_data, status_code)

        return MockHttpxResponse(self.default_response)

    def get_call_count(self) -> int:
        """API呼び出し回数を取得"""
        return len(self.call_history)

    def get_last_request(self) -> Optional[Dict[str, Any]]:
        """最後のリクエストを取得"""
        return self.call_history[-1] if self.call_history else None

    def clear_history(self):
        """呼び出し履歴をクリア"""
        self.call_history.clear()
        self.response_queue.clear()


class MockRedisClient:
    """Redisクライアントのモック"""

    def __init__(self):
        self.data = {}
        self.expiry = {}

    async def get(self, key: str) -> Optional[bytes]:
        if key in self.expiry and datetime.now() > self.expiry[key]:
            del self.data[key]
            del self.expiry[key]
            return None
        return self.data.get(key)

    async def set(self, key: str, value: bytes, ex: Optional[int] = None) -> bool:
        self.data[key] = value
        if ex:
            self.expiry[key] = datetime.now() + timedelta(seconds=ex)
        return True

    async def delete(self, key: str) -> int:
        deleted = 0
        if key in self.data:
            del self.data[key]
            deleted += 1
        if key in self.expiry:
            del self.expiry[key]
        return deleted

    async def exists(self, key: str) -> int:
        return 1 if key in self.data else 0

    async def flushdb(self) -> bool:
        self.data.clear()
        self.expiry.clear()
        return True


class TestDataFactory:
    """テストデータファクトリー"""

    @staticmethod
    def create_chat_request(
        model: str = "gpt-4",
        messages: Optional[List[Dict[str, str]]] = None,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """チャットリクエストデータを作成"""
        if messages is None:
            messages = [{"role": "user", "content": "Hello, world!"}]

        request = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }
        return request

    @staticmethod
    def create_chat_response(
        content: str = "Hello! How can I help you?",
        model: str = "gpt-4",
        finish_reason: str = "stop",
        usage: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """チャットレスポンスデータを作成"""
        if usage is None:
            usage = {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18}

        return {
            "id": "chatcmpl-test123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": finish_reason
            }],
            "usage": usage
        }

    @staticmethod
    def create_streaming_chunks(
        content: str = "Hello! How can I help you?",
        model: str = "gpt-4"
    ) -> List[Dict[str, Any]]:
        """ストリーミングチャンクデータを作成"""
        words = content.split()
        chunks = []

        # 開始チャンク
        chunks.append({
            "id": "chatcmpl-test123",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"role": "assistant", "content": ""},
                "finish_reason": None
            }]
        })

        # コンテンツチャンク
        for word in words:
            chunks.append({
                "id": "chatcmpl-test123",
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": word + " "},
                    "finish_reason": None
                }]
            })

        # 終了チャンク
        chunks.append({
            "id": "chatcmpl-test123",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        })

        return chunks

    @staticmethod
    def create_error_response(
        message: str = "Invalid request",
        error_type: str = "invalid_request_error",
        code: str = "invalid_request"
    ) -> Dict[str, Any]:
        """エラーレスポンスデータを作成"""
        return {
            "error": {
                "message": message,
                "type": error_type,
                "code": code
            }
        }


def create_mock_context_manager(mock_client):
    """AsyncContextManagerのモックを作成"""
    mock_context = AsyncMock()
    mock_context.__aenter__ = AsyncMock(return_value=mock_client)
    mock_context.__aexit__ = AsyncMock(return_value=None)
    return mock_context


# グローバルモックインスタンス
mock_azure_service = MockAzureOpenAIService()
mock_msal_app = MockPublicClientApplication("test-client-id")
mock_redis = MockRedisClient()
test_data_factory = TestDataFactory()
