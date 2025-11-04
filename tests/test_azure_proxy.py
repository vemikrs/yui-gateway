"""Tests for gateway.azure_proxy module

Tests request forwarding to Azure OpenAI API with proper authentication.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import httpx


class TestAzureOpenAIProxy:
    """Tests for AzureOpenAIProxy class"""
    
    def test_init_sets_endpoint_and_client(self, mock_settings):
        """Test that __init__ properly initializes endpoint and HTTP client"""
        with patch("gateway.azure_proxy.httpx.AsyncClient") as mock_client_class:
            from gateway.azure_proxy import AzureOpenAIProxy
            
            proxy = AzureOpenAIProxy()
            
            # Verify endpoint is set correctly (trailing slash removed)
            assert proxy.endpoint == mock_settings.azure_openai_endpoint.rstrip("/")
            
            # Verify async client was created with timeout
            mock_client_class.assert_called_once_with(timeout=120.0)
    
    @pytest.mark.asyncio
    async def test_chat_completion_success(
        self, mock_settings, mock_token, sample_chat_request, sample_chat_response
    ):
        """Test successful chat completion request"""
        with patch("gateway.azure_proxy.authenticator.get_token") as mock_get_token:
            mock_get_token.return_value = mock_token
            
            with patch("gateway.azure_proxy.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.json.return_value = sample_chat_response
                mock_response.raise_for_status = Mock()
                mock_client.post.return_value = mock_response
                mock_client_class.return_value = mock_client
                
                from gateway.azure_proxy import AzureOpenAIProxy
                proxy = AzureOpenAIProxy()
                
                result = await proxy.chat_completion(sample_chat_request)
                
                # Verify result matches expected response
                assert result == sample_chat_response
                
                # Verify token was obtained
                mock_get_token.assert_called_once()
                
                # Verify request was made with correct parameters
                mock_client.post.assert_called_once()
                call_args = mock_client.post.call_args
                
                # Check URL
                expected_url = f"{mock_settings.azure_openai_endpoint}/openai/deployments/gpt-4/chat/completions"
                assert call_args[0][0] == expected_url
                
                # Check headers
                assert call_args[1]["headers"]["Authorization"] == f"Bearer {mock_token}"
                assert call_args[1]["headers"]["Content-Type"] == "application/json"
                
                # Check params
                assert call_args[1]["params"]["api-version"] == "2024-02-15-preview"
                
                # Check body
                assert call_args[1]["json"] == sample_chat_request
                
                # Verify status was checked
                mock_response.raise_for_status.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_chat_completion_custom_model(
        self, mock_settings, mock_token, sample_chat_response
    ):
        """Test chat completion with custom model/deployment name"""
        custom_request = {
            "model": "gpt-35-turbo",
            "messages": [{"role": "user", "content": "Test"}]
        }
        
        with patch("gateway.azure_proxy.authenticator.get_token") as mock_get_token:
            mock_get_token.return_value = mock_token
            
            with patch("gateway.azure_proxy.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.json.return_value = sample_chat_response
                mock_response.raise_for_status = Mock()
                mock_client.post.return_value = mock_response
                mock_client_class.return_value = mock_client
                
                from gateway.azure_proxy import AzureOpenAIProxy
                proxy = AzureOpenAIProxy()
                
                await proxy.chat_completion(custom_request)
                
                # Verify URL uses custom deployment name
                call_args = mock_client.post.call_args
                expected_url = f"{mock_settings.azure_openai_endpoint}/openai/deployments/gpt-35-turbo/chat/completions"
                assert call_args[0][0] == expected_url
    
    @pytest.mark.asyncio
    async def test_chat_completion_http_error(
        self, mock_settings, mock_token, sample_chat_request
    ):
        """Test handling of HTTP errors from Azure OpenAI"""
        with patch("gateway.azure_proxy.authenticator.get_token") as mock_get_token:
            mock_get_token.return_value = mock_token
            
            with patch("gateway.azure_proxy.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.status_code = 401
                mock_response.text = "Unauthorized"
                mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                    "401 Unauthorized",
                    request=Mock(),
                    response=mock_response
                )
                mock_client.post.return_value = mock_response
                mock_client_class.return_value = mock_client
                
                from gateway.azure_proxy import AzureOpenAIProxy
                proxy = AzureOpenAIProxy()
                
                with pytest.raises(httpx.HTTPStatusError):
                    await proxy.chat_completion(sample_chat_request)
    
    @pytest.mark.asyncio
    async def test_chat_completion_network_error(
        self, mock_settings, mock_token, sample_chat_request
    ):
        """Test handling of network errors"""
        with patch("gateway.azure_proxy.authenticator.get_token") as mock_get_token:
            mock_get_token.return_value = mock_token
            
            with patch("gateway.azure_proxy.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client.post.side_effect = httpx.ConnectError("Connection failed")
                mock_client_class.return_value = mock_client
                
                from gateway.azure_proxy import AzureOpenAIProxy
                proxy = AzureOpenAIProxy()
                
                with pytest.raises(httpx.ConnectError):
                    await proxy.chat_completion(sample_chat_request)
    
    @pytest.mark.asyncio
    async def test_chat_completion_token_acquisition_failure(
        self, mock_settings, sample_chat_request
    ):
        """Test handling of token acquisition failures"""
        with patch("gateway.azure_proxy.authenticator.get_token") as mock_get_token:
            mock_get_token.side_effect = Exception("Token acquisition failed")
            
            from gateway.azure_proxy import AzureOpenAIProxy
            proxy = AzureOpenAIProxy()
            
            with pytest.raises(Exception) as exc_info:
                await proxy.chat_completion(sample_chat_request)
            
            assert "Token acquisition failed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_close_closes_client(self, mock_settings):
        """Test that close() properly closes the HTTP client"""
        with patch("gateway.azure_proxy.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            from gateway.azure_proxy import AzureOpenAIProxy
            proxy = AzureOpenAIProxy()
            
            await proxy.close()
            
            mock_client.aclose.assert_called_once()
    
    def test_singleton_proxy_exists(self):
        """Test that singleton proxy instance is available"""
        from gateway.azure_proxy import proxy
        
        assert proxy is not None
        assert hasattr(proxy, "chat_completion")
        assert hasattr(proxy, "close")
        assert hasattr(proxy, "endpoint")
        assert hasattr(proxy, "client")
    
    @pytest.mark.asyncio
    async def test_chat_completion_default_model(
        self, mock_settings, mock_token, sample_chat_response
    ):
        """Test that default model is used when not specified"""
        request_without_model = {
            "messages": [{"role": "user", "content": "Test"}]
        }
        
        with patch("gateway.azure_proxy.authenticator.get_token") as mock_get_token:
            mock_get_token.return_value = mock_token
            
            with patch("gateway.azure_proxy.httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_response = AsyncMock()
                mock_response.json.return_value = sample_chat_response
                mock_response.raise_for_status = Mock()
                mock_client.post.return_value = mock_response
                mock_client_class.return_value = mock_client
                
                from gateway.azure_proxy import AzureOpenAIProxy
                proxy = AzureOpenAIProxy()
                
                await proxy.chat_completion(request_without_model)
                
                # Verify URL uses default model (gpt-4)
                call_args = mock_client.post.call_args
                expected_url = f"{mock_settings.azure_openai_endpoint}/openai/deployments/gpt-4/chat/completions"
                assert call_args[0][0] == expected_url
    
    @pytest.mark.asyncio
    async def test_chat_completion_strips_trailing_slash(self, mock_token, sample_chat_request, sample_chat_response):
        """Test that trailing slash in endpoint is properly handled"""
        with patch("gateway.azure_proxy.settings") as mock_settings_module:
            # Endpoint WITH trailing slash
            mock_settings_module.azure_openai_endpoint = "https://test.openai.azure.com/"
            
            with patch("gateway.azure_proxy.authenticator.get_token") as mock_get_token:
                mock_get_token.return_value = mock_token
                
                with patch("gateway.azure_proxy.httpx.AsyncClient") as mock_client_class:
                    mock_client = AsyncMock()
                    mock_response = AsyncMock()
                    mock_response.json.return_value = sample_chat_response
                    mock_response.raise_for_status = Mock()
                    mock_client.post.return_value = mock_response
                    mock_client_class.return_value = mock_client
                    
                    from gateway.azure_proxy import AzureOpenAIProxy
                    proxy = AzureOpenAIProxy()
                    
                    await proxy.chat_completion(sample_chat_request)
                    
                    # Verify URL doesn't have double slashes
                    call_args = mock_client.post.call_args
                    url = call_args[0][0]
                    assert "//" not in url.replace("https://", "")
