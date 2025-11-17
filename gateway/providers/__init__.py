"""Provider abstraction layer

複数のLLMプロバイダー（Azure OpenAI、OpenAI、Claude等）を
統一インターフェースで扱うための抽象化層。
"""

from gateway.providers.base import (
    LLMProvider,
    ProviderConfig,
    ProviderError,
    ModelNotFoundError,
    AuthenticationError,
    RateLimitError,
    Message,
    ChatRequest,
    ChatResponse,
)
from gateway.providers.factory import (
    ProviderFactory,
    ProviderRegistry,
    ProviderType,
    provider_factory,
)
from gateway.providers.azure_openai import (
    AzureOpenAIProvider,
    AzureOpenAIConfig,
)

__all__ = [
    # Base classes
    "LLMProvider",
    "ProviderConfig",
    "ProviderError",
    "ModelNotFoundError",
    "AuthenticationError",
    "RateLimitError",
    "Message",
    "ChatRequest",
    "ChatResponse",
    # Factory
    "ProviderFactory",
    "ProviderRegistry",
    "ProviderType",
    "provider_factory",
    # Providers
    "AzureOpenAIProvider",
    "AzureOpenAIConfig",
]
