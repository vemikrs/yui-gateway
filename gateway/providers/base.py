"""Abstract provider interface

LLMプロバイダーの共通インターフェースを定義する。
新しいプロバイダーはこのインターフェースを実装することで
既存システムとシームレスに統合できる。
"""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel


class Message(BaseModel):
    """Universal message format"""
    role: str
    content: str


class ChatRequest(BaseModel):
    """Universal chat request format"""
    model: str
    messages: List[Message]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    # Additional parameters can be added as needed


class ChatResponse(BaseModel):
    """Universal chat response format"""
    id: str
    object: str
    created: int
    model: str
    choices: List[Dict[str, Any]]
    usage: Optional[Dict[str, Any]] = None


class ProviderConfig(BaseModel):
    """Base configuration for providers"""
    name: str
    enabled: bool = True
    timeout: float = 120.0
    retry_attempts: int = 3


class LLMProvider(ABC):
    """Abstract base class for LLM providers

    This interface ensures consistent behavior across different LLM providers
    (Azure OpenAI, OpenAI, Claude, etc.) while allowing provider-specific
    implementations.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.name

    @abstractmethod
    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Execute a chat completion request

        Args:
            request: Universal chat request

        Returns:
            ChatResponse: Universal chat response

        Raises:
            ProviderError: When the provider request fails
        """
        pass

    @abstractmethod
    async def chat_completion_stream(self, request: ChatRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute a streaming chat completion request

        Args:
            request: Universal chat request with stream=True

        Yields:
            Dict[str, Any]: Streaming response chunks in OpenAI format

        Raises:
            ProviderError: When the provider request fails
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[str]:
        """List available models for this provider

        Returns:
            List[str]: Available model names
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider availability

        Returns:
            bool: True if provider is healthy
        """
        pass

    @abstractmethod
    async def close(self):
        """Clean up provider resources"""
        pass


class ProviderError(Exception):
    """Base exception for provider errors"""

    def __init__(self, message: str, provider: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class ModelNotFoundError(ProviderError):
    """Raised when a requested model is not available"""
    pass


class AuthenticationError(ProviderError):
    """Raised when provider authentication fails"""
    pass


class RateLimitError(ProviderError):
    """Raised when provider rate limits are exceeded"""
    pass
