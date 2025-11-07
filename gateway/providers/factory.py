"""Provider factory and registry

Manages provider instances and configuration.
Supports dynamic provider switching and fallback scenarios.
"""

import logging
from typing import Dict, List, Optional, Type, Union
from enum import Enum

from gateway.providers.base import LLMProvider, ProviderConfig, ProviderError
from gateway.providers.azure_openai import AzureOpenAIProvider, AzureOpenAIConfig

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported provider types"""
    AZURE_OPENAI = "azure_openai"
    OPENAI = "openai"  # Future implementation
    CLAUDE = "claude"  # Future implementation


class ProviderRegistry:
    """Registry for LLM providers"""

    _providers: Dict[ProviderType, Type[LLMProvider]] = {
        ProviderType.AZURE_OPENAI: AzureOpenAIProvider,
        # Future providers will be registered here
    }

    _configs: Dict[ProviderType, Type[ProviderConfig]] = {
        ProviderType.AZURE_OPENAI: AzureOpenAIConfig,
    }

    @classmethod
    def get_provider_class(cls, provider_type: ProviderType) -> Type[LLMProvider]:
        """Get provider class by type"""
        if provider_type not in cls._providers:
            raise ValueError(f"Unsupported provider type: {provider_type}")
        return cls._providers[provider_type]

    @classmethod
    def get_config_class(cls, provider_type: ProviderType) -> Type[ProviderConfig]:
        """Get config class by type"""
        if provider_type not in cls._configs:
            raise ValueError(f"Unsupported provider type: {provider_type}")
        return cls._configs[provider_type]

    @classmethod
    def register_provider(
        cls,
        provider_type: ProviderType,
        provider_class: Type[LLMProvider],
        config_class: Type[ProviderConfig]
    ):
        """Register a new provider type"""
        cls._providers[provider_type] = provider_class
        cls._configs[provider_type] = config_class
        logger.info(f"Registered provider: {provider_type.value}")


class ProviderFactory:
    """Factory for creating and managing provider instances"""

    def __init__(self):
        self._instances: Dict[str, LLMProvider] = {}
        self._primary_provider: Optional[LLMProvider] = None
        self._fallback_providers: List[LLMProvider] = []

    async def create_provider(
        self,
        provider_type: ProviderType,
        config: Union[ProviderConfig, Dict],
        instance_name: Optional[str] = None
    ) -> LLMProvider:
        """Create a provider instance"""

        provider_class = ProviderRegistry.get_provider_class(provider_type)
        config_class = ProviderRegistry.get_config_class(provider_type)

        # Convert dict config to proper config object if needed
        if isinstance(config, dict):
            config = config_class(**config)

        # Create provider instance
        provider = provider_class(config)

        # Store instance if name provided
        if instance_name:
            self._instances[instance_name] = provider
            logger.info(f"Created provider instance: {instance_name} ({provider_type.value})")

        return provider

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Get provider instance by name"""
        return self._instances.get(name)

    def set_primary_provider(self, provider: LLMProvider):
        """Set the primary provider"""
        self._primary_provider = provider
        logger.info(f"Set primary provider: {provider.name}")

    def add_fallback_provider(self, provider: LLMProvider):
        """Add a fallback provider"""
        self._fallback_providers.append(provider)
        logger.info(f"Added fallback provider: {provider.name}")

    def get_primary_provider(self) -> Optional[LLMProvider]:
        """Get the primary provider"""
        return self._primary_provider

    def get_fallback_providers(self) -> List[LLMProvider]:
        """Get fallback providers"""
        return self._fallback_providers.copy()

    async def close_all(self):
        """Close all provider instances"""
        for name, provider in self._instances.items():
            try:
                await provider.close()
                logger.info(f"Closed provider: {name}")
            except Exception as e:
                logger.error(f"Error closing provider {name}: {e}")

        self._instances.clear()
        self._primary_provider = None
        self._fallback_providers.clear()


# Global provider factory instance
provider_factory = ProviderFactory()
