# YuiGateway

Secure Entra ID-based proxy for Azure OpenAI.

## Quick Start

```bash
# 1. Clone and install dependencies
git clone https://github.com/vemikrs/yui-gateway.git
cd yui-gateway
poetry install  # or: pip install -e .

# 2. Automatic Azure setup (recommended)
python scripts/provision_env.py --login interactive --select
# This creates Azure app registration, service principal, RBAC, and .env file

# 3. Start the server
bash scripts/start_local.sh
# Auto-provisions if .env is missing, then starts server on port 8000

# 4. Check available deployments
python scripts/list_deployments.py

# 5. Test the connection
curl http://localhost:8000/health
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-5-mini", "messages": [{"role": "user", "content": "Hello!"}], "max_completion_tokens": 50}'
```

## Documentation

- **[Local Usage Guide (Japanese)](docs/LOCAL_USAGE.md)** - ローカル環境での詳細な使用方法（自動プロビジョニング対応）
- **[Local Usage Guide (English)](docs/LOCAL_USAGE_EN.md)** - Detailed local usage instructions
- **[Setup Guide](SETUP.md)** - Manual setup and configuration
- **[Architecture Overview](docs/overview.md)** - System architecture and design
- **[Use Cases](docs/use-cases.md)** - Example use cases
- **[Development Guide](gateway/README.dev.md)** - Development and customization
- **[Testing Guide](TESTING.md)** - Running tests and validation

### Utility Scripts
- `scripts/provision_env.py` - Automatic Azure resource provisioning
- `scripts/list_deployments.py` - List available Azure OpenAI deployments
- `scripts/start_local.sh` - Start server with auto-provisioning fallback

## Features

- ✅ **Secure Authentication** - Uses Entra ID (Azure AD) instead of API keys
- ✅ **OpenAI Compatible** - Standard OpenAI API interface with model-specific parameters
- ✅ **Token Management** - Automatic token refresh and caching
- ✅ **Auto Provisioning** - One-click Azure resource setup and configuration
- ✅ **Deployment Discovery** - Automatically detect available Azure OpenAI models and versions
- ✅ **Multi-Login Support** - Interactive, CLI, and device code authentication
- ✅ **VS Code Integration** - Built-in tasks for seamless development
- ✅ **Easy Integration** - Works with any OpenAI-compatible client
- ✅ **Local Proxy** - Run on your local machine for development

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=gateway --cov-report=html

# Run specific tests
pytest tests/test_routes.py -v
```

See [tests/README.md](tests/README.md) for more details.

## License

See LICENSE file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/vemikrs/yui-gateway/issues)
- **Documentation**: [docs/](docs/)
- **Related Project**: [YuiHub](https://github.com/vemikrs/yuihub)
