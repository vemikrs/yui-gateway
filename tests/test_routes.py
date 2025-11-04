"""Tests for gateway.routes module

Tests FastAPI endpoints and request/response handling.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient
import httpx


@pytest.fixture
def client():
    """FastAPI test client"""
    from gateway.routes import app
    return TestClient(app)


class TestRootEndpoint:
    """Tests for root endpoint"""
    
    def test_root_returns_service_info(self, client):
        """Test that root endpoint returns service information"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "YuiGateway"
        assert data["version"] == "0.1.0"
        assert "description" in data
        assert "endpoints" in data
        assert "/v1/chat/completions" in data["endpoints"]
    
    def test_root_returns_json(self, client):
        """Test that root endpoint returns JSON"""
        response = client.get("/")
        
        assert response.headers["content-type"] == "application/json"


class TestHealthEndpoint:
    """Tests for health check endpoint"""
    
    def test_health_returns_healthy_status(self, client):
        """Test that health endpoint returns healthy status"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "healthy"
    
    def test_health_returns_json(self, client):
        """Test that health endpoint returns JSON"""
        response = client.get("/health")
        
        assert response.headers["content-type"] == "application/json"


class TestChatCompletionsEndpoint:
    """Tests for /v1/chat/completions endpoint"""
    
    def test_chat_completions_success(self, client, sample_chat_request, sample_chat_response):
        """Test successful chat completion request"""
        with patch("gateway.routes.proxy.chat_completion") as mock_chat:
            mock_chat.return_value = sample_chat_response
            
            response = client.post("/v1/chat/completions", json=sample_chat_request)
            
            assert response.status_code == 200
            data = response.json()
            
            assert data == sample_chat_response
            assert data["choices"][0]["message"]["content"] == "Hello! How can I help you today?"
            
            # Verify proxy was called with correct data
            mock_chat.assert_called_once()
            call_args = mock_chat.call_args[0][0]
            assert call_args["model"] == "gpt-4"
            assert len(call_args["messages"]) == 2
    
    def test_chat_completions_with_optional_params(self, client, sample_chat_response):
        """Test chat completion with optional parameters"""
        request_data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Test"}],
            "temperature": 0.5,
            "max_tokens": 50,
            "top_p": 0.9,
            "presence_penalty": 0.1,
            "frequency_penalty": 0.2,
            "n": 1
        }
        
        with patch("gateway.routes.proxy.chat_completion") as mock_chat:
            mock_chat.return_value = sample_chat_response
            
            response = client.post("/v1/chat/completions", json=request_data)
            
            assert response.status_code == 200
            
            # Verify all parameters were passed through
            call_args = mock_chat.call_args[0][0]
            assert call_args["temperature"] == 0.5
            assert call_args["max_tokens"] == 50
            assert call_args["top_p"] == 0.9
    
    def test_chat_completions_missing_model_field(self, client):
        """Test that missing model field returns validation error"""
        invalid_request = {
            "messages": [{"role": "user", "content": "Test"}]
        }
        
        response = client.post("/v1/chat/completions", json=invalid_request)
        
        assert response.status_code == 422  # Validation error
    
    def test_chat_completions_missing_messages_field(self, client):
        """Test that missing messages field returns validation error"""
        invalid_request = {
            "model": "gpt-4"
        }
        
        response = client.post("/v1/chat/completions", json=invalid_request)
        
        assert response.status_code == 422  # Validation error
    
    def test_chat_completions_invalid_message_format(self, client):
        """Test that invalid message format returns validation error"""
        invalid_request = {
            "model": "gpt-4",
            "messages": [
                {"role": "user"}  # Missing content
            ]
        }
        
        response = client.post("/v1/chat/completions", json=invalid_request)
        
        assert response.status_code == 422  # Validation error
    
    def test_chat_completions_proxy_error(self, client, sample_chat_request):
        """Test handling of proxy errors"""
        with patch("gateway.routes.proxy.chat_completion") as mock_chat:
            mock_chat.side_effect = Exception("Azure OpenAI service unavailable")
            
            response = client.post("/v1/chat/completions", json=sample_chat_request)
            
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Failed to process request" in data["detail"]
    
    def test_chat_completions_exclude_none_values(self, client, sample_chat_response):
        """Test that None values are excluded from proxy request"""
        request_with_none = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Test"}],
            "max_tokens": None,  # Should be excluded
            "temperature": 0.7   # Should be included
        }
        
        with patch("gateway.routes.proxy.chat_completion") as mock_chat:
            mock_chat.return_value = sample_chat_response
            
            response = client.post("/v1/chat/completions", json=request_with_none)
            
            assert response.status_code == 200
            
            # Verify None values were excluded
            call_args = mock_chat.call_args[0][0]
            assert "max_tokens" not in call_args
            assert call_args["temperature"] == 0.7
    
    def test_chat_completions_stream_not_supported(self, client, sample_chat_request):
        """Test that streaming is specified in request (not yet implemented)"""
        # Note: This test documents current behavior
        # Streaming support is a future enhancement
        stream_request = {**sample_chat_request, "stream": True}
        
        with patch("gateway.routes.proxy.chat_completion") as mock_chat:
            # For now, stream parameter is passed through
            mock_chat.return_value = {"choices": []}
            
            response = client.post("/v1/chat/completions", json=stream_request)
            
            # Request is accepted even with stream=True
            assert response.status_code == 200
    
    def test_chat_completions_multiple_messages(self, client, sample_chat_response):
        """Test chat completion with multiple messages"""
        multi_message_request = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there!"},
                {"role": "user", "content": "How are you?"}
            ]
        }
        
        with patch("gateway.routes.proxy.chat_completion") as mock_chat:
            mock_chat.return_value = sample_chat_response
            
            response = client.post("/v1/chat/completions", json=multi_message_request)
            
            assert response.status_code == 200
            
            # Verify all messages were passed
            call_args = mock_chat.call_args[0][0]
            assert len(call_args["messages"]) == 4
    
    def test_chat_completions_returns_json(self, client, sample_chat_request, sample_chat_response):
        """Test that chat completions endpoint returns JSON"""
        with patch("gateway.routes.proxy.chat_completion") as mock_chat:
            mock_chat.return_value = sample_chat_response
            
            response = client.post("/v1/chat/completions", json=sample_chat_request)
            
            assert "application/json" in response.headers["content-type"]


class TestApplicationLifecycle:
    """Tests for application lifecycle events"""
    
    @pytest.mark.asyncio
    async def test_shutdown_closes_proxy(self):
        """Test that shutdown event closes the proxy"""
        with patch("gateway.routes.proxy.close") as mock_close:
            from gateway.routes import shutdown_event
            
            await shutdown_event()
            
            mock_close.assert_called_once()


class TestMessageModel:
    """Tests for Message Pydantic model"""
    
    def test_message_model_valid(self):
        """Test valid message creation"""
        from gateway.routes import Message
        
        msg = Message(role="user", content="Hello")
        
        assert msg.role == "user"
        assert msg.content == "Hello"
    
    def test_message_model_missing_role(self):
        """Test that missing role raises validation error"""
        from gateway.routes import Message
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            Message(content="Hello")
    
    def test_message_model_missing_content(self):
        """Test that missing content raises validation error"""
        from gateway.routes import Message
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            Message(role="user")


class TestChatCompletionRequestModel:
    """Tests for ChatCompletionRequest Pydantic model"""
    
    def test_request_model_minimal(self):
        """Test minimal valid request"""
        from gateway.routes import ChatCompletionRequest
        
        req = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Test"}]
        )
        
        assert req.model == "gpt-4"
        assert len(req.messages) == 1
        # Check defaults
        assert req.temperature == 1.0
        assert req.top_p == 1.0
        assert req.n == 1
        assert req.stream is False
        assert req.max_tokens is None
    
    def test_request_model_all_fields(self):
        """Test request with all fields"""
        from gateway.routes import ChatCompletionRequest
        
        req = ChatCompletionRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "Test"}],
            temperature=0.5,
            top_p=0.9,
            n=2,
            stream=True,
            max_tokens=100,
            presence_penalty=0.1,
            frequency_penalty=0.2
        )
        
        assert req.temperature == 0.5
        assert req.top_p == 0.9
        assert req.n == 2
        assert req.stream is True
        assert req.max_tokens == 100
        assert req.presence_penalty == 0.1
        assert req.frequency_penalty == 0.2
