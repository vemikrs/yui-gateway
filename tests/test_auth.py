"""Tests for gateway.auth module

Tests Entra ID (Azure AD) token acquisition using MSAL.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestEntraIDAuthenticator:
    """Tests for EntraIDAuthenticator class"""

    def test_init_creates_msal_app(self, mock_settings):
        """Test that __init__ creates a ConfidentialClientApplication"""
        with patch("gateway.auth.ConfidentialClientApplication") as mock_app_class:
            # Ensure settings are properly mocked
            with patch("gateway.auth.settings", mock_settings):
                from gateway.auth import EntraIDAuthenticator

                authenticator = EntraIDAuthenticator()

                # Verify MSAL app was created with correct parameters
                mock_app_class.assert_called_once_with(
                    client_id=mock_settings.client_id,
                    client_credential=mock_settings.client_secret,
                    authority=f"https://login.microsoftonline.com/{mock_settings.tenant_id}",
                )

                # Verify scope was set
                assert authenticator.scope == [mock_settings.scope]

    def test_get_token_from_cache_success(self, mock_settings, mock_token):
        """Test successful token retrieval from cache"""
        with patch("gateway.auth.ConfidentialClientApplication") as mock_app_class:
            mock_app = MagicMock()
            mock_app.acquire_token_silent.return_value = {"access_token": mock_token}
            mock_app_class.return_value = mock_app

            from gateway.auth import EntraIDAuthenticator

            authenticator = EntraIDAuthenticator()

            token = authenticator.get_token()

            assert token == mock_token
            mock_app.acquire_token_silent.assert_called_once()
            # Should not call acquire_token_for_client if cache hit
            mock_app.acquire_token_for_client.assert_not_called()

    def test_get_token_cache_miss_acquires_new(self, mock_settings, mock_token):
        """Test token acquisition when cache misses"""
        with patch("gateway.auth.ConfidentialClientApplication") as mock_app_class:
            mock_app = MagicMock()
            # Cache miss
            mock_app.acquire_token_silent.return_value = None
            # Successful new token acquisition
            mock_app.acquire_token_for_client.return_value = {
                "access_token": mock_token
            }
            mock_app_class.return_value = mock_app

            from gateway.auth import EntraIDAuthenticator

            authenticator = EntraIDAuthenticator()

            token = authenticator.get_token()

            assert token == mock_token
            mock_app.acquire_token_silent.assert_called_once()
            mock_app.acquire_token_for_client.assert_called_once_with(
                scopes=[mock_settings.scope]
            )

    def test_get_token_failure_raises_exception(self, mock_settings):
        """Test that token acquisition failure raises an exception"""
        with patch("gateway.auth.ConfidentialClientApplication") as mock_app_class:
            mock_app = MagicMock()
            mock_app.acquire_token_silent.return_value = None
            # Simulate authentication failure
            mock_app.acquire_token_for_client.return_value = {
                "error": "invalid_client",
                "error_description": "Invalid client credentials",
            }
            mock_app_class.return_value = mock_app

            from gateway.auth import EntraIDAuthenticator

            authenticator = EntraIDAuthenticator()

            with pytest.raises(Exception) as exc_info:
                authenticator.get_token()

            assert "Token acquisition failed" in str(exc_info.value)
            assert "Invalid client credentials" in str(exc_info.value)

    def test_get_token_with_error_only(self, mock_settings):
        """Test error handling when only error field is present"""
        with patch("gateway.auth.ConfidentialClientApplication") as mock_app_class:
            mock_app = MagicMock()
            mock_app.acquire_token_silent.return_value = None
            mock_app.acquire_token_for_client.return_value = {
                "error": "unauthorized_client"
            }
            mock_app_class.return_value = mock_app

            from gateway.auth import EntraIDAuthenticator

            authenticator = EntraIDAuthenticator()

            with pytest.raises(Exception) as exc_info:
                authenticator.get_token()

            assert "unauthorized_client" in str(exc_info.value)

    def test_singleton_authenticator_exists(self, mock_settings):
        """Test that singleton authenticator instance is available"""
        with patch("gateway.auth.ConfidentialClientApplication"):
            from gateway.auth import get_authenticator

            authenticator = get_authenticator()

            assert authenticator is not None
            assert hasattr(authenticator, "get_token")
            assert hasattr(authenticator, "app")
            assert hasattr(authenticator, "scope")

    def test_get_token_returns_string(self, mock_settings, mock_token):
        """Test that get_token returns a string token"""
        with patch("gateway.auth.ConfidentialClientApplication") as mock_app_class:
            mock_app = MagicMock()
            mock_app.acquire_token_silent.return_value = {"access_token": mock_token}
            mock_app_class.return_value = mock_app

            from gateway.auth import EntraIDAuthenticator

            authenticator = EntraIDAuthenticator()

            token = authenticator.get_token()

            assert isinstance(token, str)
            # Token should NOT include "Bearer " prefix
            assert not token.startswith("Bearer ")
