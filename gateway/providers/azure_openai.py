"""Azure OpenAI provider implementation

Azure OpenAI specific implementation of the LLM provider interface.
Handles Azure-specific authentication, model mapping, and API quirks.
"""

import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from pydantic import BaseModel

from gateway import auth
from gateway.providers.base import (
    LLMProvider, ChatRequest, ChatResponse, ProviderConfig,
    ProviderError, ModelNotFoundError, AuthenticationError
)

logger = logging.getLogger(__name__)


class AzureOpenAIConfig(ProviderConfig):
    """Azure OpenAI specific configuration"""
    endpoint: str
    api_version: str = "2024-10-21"
    model_mapping: Dict[str, str] = {
        "gpt-4": "gpt-5-mini",
        "gpt-4o": "gpt-5-mini",
        "gpt-4-turbo": "gpt-5-mini",
        "gpt-3.5-turbo": "gpt-5-mini",
        "gpt-5-mini": "gpt-5-mini"
    }


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI implementation of LLM provider"""

    def __init__(self, config: AzureOpenAIConfig, authenticator=None):
        super().__init__(config)
        self.config: AzureOpenAIConfig = config
        self.authenticator = authenticator or auth.get_authenticator()
        self.client = httpx.AsyncClient(timeout=config.timeout)
        self.endpoint = config.endpoint.rstrip("/")

        logger.info(f"AzureOpenAIProvider initialized for endpoint: {self.endpoint}")

    async def chat_completion(self, request: ChatRequest) -> ChatResponse:
        """Execute non-streaming chat completion"""
        try:
            token = self.authenticator.get_token()
            deployment_name = self._get_deployment_name(request.model)

            url = f"{self.endpoint}/openai/deployments/{deployment_name}/chat/completions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            params = {"api-version": self.config.api_version}

            # Convert universal request to Azure format
            azure_request = self._convert_to_azure_request(request)

            logger.info(f"Azure OpenAI request: {request.model} -> {deployment_name}")

            response = await self.client.post(url, json=azure_request, headers=headers, params=params)
            response.raise_for_status()

            result = response.json()
            return self._convert_from_azure_response(result)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                available_models = list(self.config.model_mapping.keys())
                raise ModelNotFoundError(
                    f"Model '{request.model}' not found. Available: {available_models}",
                    provider=self.name,
                    status_code=404
                )
            elif e.response.status_code == 401:
                raise AuthenticationError(
                    "Authentication failed with Azure OpenAI",
                    provider=self.name,
                    status_code=401
                )
            else:
                raise ProviderError(
                    f"Azure OpenAI error: {e.response.status_code} - {e.response.text}",
                    provider=self.name,
                    status_code=e.response.status_code
                )
        except Exception as e:
            raise ProviderError(f"Unexpected error: {str(e)}", provider=self.name)

    async def chat_completion_stream(self, request: ChatRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """Execute streaming chat completion"""
        try:
            token = self.authenticator.get_token()
            deployment_name = self._get_deployment_name(request.model)

            url = f"{self.endpoint}/openai/deployments/{deployment_name}/chat/completions"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream"
            }
            params = {"api-version": self.config.api_version}

            # Convert to Azure format with streaming enabled
            azure_request = self._convert_to_azure_request(request)
            azure_request["stream"] = True

            logger.info(f"Azure OpenAI streaming: {request.model} -> {deployment_name}")

            async with self.client.stream("POST", url, json=azure_request, headers=headers, params=params) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.strip():
                        if line.startswith("data: "):
                            data_str = line[6:]

                            if data_str.strip() == "[DONE]":
                                break

                            try:
                                chunk_data = json.loads(data_str)
                                converted_chunk = self._convert_azure_chunk_to_openai(chunk_data)
                                if converted_chunk:
                                    yield converted_chunk
                            except json.JSONDecodeError:
                                continue

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ModelNotFoundError(
                    f"Model '{request.model}' not found for streaming",
                    provider=self.name,
                    status_code=404
                )
            else:
                raise ProviderError(
                    f"Azure OpenAI streaming error: {e.response.status_code}",
                    provider=self.name,
                    status_code=e.response.status_code
                )
        except Exception as e:
            raise ProviderError(f"Streaming error: {str(e)}", provider=self.name)

    async def list_models(self) -> List[str]:
        """List available models (mapped names)"""
        return list(self.config.model_mapping.keys())

    async def health_check(self) -> bool:
        """Check Azure OpenAI availability"""
        try:
            token = self.authenticator.get_token()
            # Use a minimal request to check connectivity
            test_request = ChatRequest(
                model="gpt-4",
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            await self.chat_completion(test_request)
            return True
        except Exception:
            return False

    async def close(self):
        """Clean up HTTP client"""
        await self.client.aclose()

    def _get_deployment_name(self, model: str) -> str:
        """Get Azure deployment name from model name"""
        return self.config.model_mapping.get(model, model)

    def _convert_to_azure_request(self, request: ChatRequest) -> Dict[str, Any]:
        """Convert universal request to Azure OpenAI format"""
        return request.model_dump(exclude_none=True)

    def _convert_from_azure_response(self, response: Dict[str, Any]) -> ChatResponse:
        """Convert Azure response to universal format"""
        return ChatResponse(**response)

    def _convert_azure_chunk_to_openai(self, azure_chunk: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Convert Azure streaming chunk to OpenAI format"""
        # Azure OpenAI uses same format as OpenAI, so minimal conversion needed
        return azure_chunk if azure_chunk else None
