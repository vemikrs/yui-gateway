# YuiGateway

Secure Entra ID-based proxy for Azure OpenAI.

## Quick Start

```bash
# 1. Clone and install dependencies
git clone https://github.com/vemikrs/yui-gateway.git
cd yui-gateway
poetry install  # or: pip install -e .

# 2. Configure environment
cp .env.template .env
# Edit .env with your Azure credentials

# 3. Start the server
bash scripts/start_local.sh
# or: uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000

# 4. Test the connection
curl http://localhost:8000/health
```

## Documentation

- **[Local Usage Guide (Japanese)](docs/LOCAL_USAGE.md)** - ローカル環境での詳細な使用方法
- **[Local Usage Guide (English)](docs/LOCAL_USAGE_EN.md)** - Detailed local usage instructions
- **[Setup Guide](SETUP.md)** - Initial setup and configuration
- **[Architecture Overview](docs/overview.md)** - System architecture and design
- **[Use Cases](docs/use-cases.md)** - Example use cases
- **[Development Guide](gateway/README.dev.md)** - Development and customization

## Features

- ✅ **Secure Authentication** - Uses Entra ID (Azure AD) instead of API keys
- ✅ **OpenAI Compatible** - Standard OpenAI API interface
- ✅ **Token Management** - Automatic token refresh and caching
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
