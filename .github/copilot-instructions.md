# GitHub Copilot Instructions for YuiGateway

YuiGateway is a **local AI proxy** that securely connects to Azure OpenAI using Entra ID (Azure AD) authentication. It provides an OpenAI-compatible API without exposing API keys, designed as the "model execution layer" for the [YuiHub](https://github.com/vemikrs/yuihub) thought recording platform.

## Project Philosophy

This project follows YuiHub's design principles:
- **Record the "why"**, not just the "what" - Document decision rationale in comments and commit messages
- **Security first** - Never expose API keys; use token-based authentication
- **Extensibility** - Design for future model switching and plugin support
- **Opt-in transparency** - Logging is private by default, analyzable by choice

## Technology Stack

- **Language**: Python 3.10+
- **Framework**: FastAPI (async/await pattern)
- **Authentication**: Microsoft Authentication Library (MSAL)
- **HTTP Client**: httpx (async)
- **Configuration**: Pydantic Settings with .env
- **Deployment**: Uvicorn (ASGI server)

## Code Standards

### Python Style
- Follow PEP 8 conventions
- Use type hints for all function signatures
- Prefer f-strings for string formatting
- Use descriptive variable names (avoid single letters except in comprehensions)
- Import order: stdlib → third-party → local (separated by blank lines)

### Async Patterns
- Use `async`/`await` consistently for I/O operations
- Never use blocking calls in async functions
- Prefer `httpx.AsyncClient` over `requests`
- Use `asyncio.gather()` for concurrent operations when appropriate

### Error Handling
- Use specific exception types, not bare `except:`
- Log errors with context before raising or handling
- Provide meaningful error messages to API clients
- Never expose internal credentials or tokens in error responses

### Documentation
- Add docstrings to all public functions and classes (Google style)
- Include Args, Returns, and Raises sections in docstrings
- Document "why" decisions in comments, not "what" (code shows what)
- Update `docs/` when making architectural changes

### Testing
- Write pytest-based tests for new functionality
- Use `pytest-asyncio` for async test cases
- Mock external dependencies (Azure AD, Azure OpenAI)
- Test both success and error paths
- Place tests in `tests/` directory with `test_*.py` naming

## Development Workflow

### Before Committing
```bash
# Format code (when black is installed)
black gateway/

# Run tests
pytest tests/

# Check for errors
python -m py_compile gateway/*.py
```

### Building and Running
```bash
# Install dependencies
poetry install

# Copy and configure environment
cp .env.template .env
# Edit .env with your Azure credentials

# Start development server
bash scripts/start_local.sh

# Or run directly
uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000
```

## Repository Structure

- `gateway/` - Main application code
  - `routes.py` - FastAPI endpoints (OpenAI-compatible API)
  - `auth.py` - Entra ID token acquisition (MSAL)
  - `azure_proxy.py` - Request forwarding to Azure OpenAI
  - `settings.py` - Configuration management (Pydantic)
- `tests/` - Test suite
- `scripts/` - Helper scripts (startup, deployment)
- `docs/` - Documentation and architecture notes
- `meta/` - Project philosophy and design principles

## Key Guidelines

1. **Security**: Never log or expose tokens, credentials, or user data
2. **Compatibility**: Maintain OpenAI API compatibility for `/v1/chat/completions`
3. **Idiomatic Python**: Use context managers, comprehensions, and type hints
4. **Async-first**: All I/O operations should be async
5. **Logging**: Use structured logging with appropriate levels (DEBUG/INFO/ERROR)
6. **Configuration**: All secrets and endpoints go in .env, never hardcode
7. **Error messages**: Be specific and actionable, especially for auth/config errors
8. **Comments**: Explain why a choice was made, especially for non-obvious patterns

## Common Patterns

### Adding a New Endpoint
1. Define Pydantic request/response models in `routes.py`
2. Create the FastAPI route handler with proper type hints
3. Call the appropriate service (auth, proxy) with error handling
4. Add logging for debugging (INFO for requests, ERROR for failures)
5. Write tests covering success and error cases

### Extending to New Models
1. Add configuration in `settings.py` for the new model endpoint
2. Create a new proxy class in a separate file (e.g., `openai_proxy.py`)
3. Implement the same interface as `AzureOpenAIProxy`
4. Update `routes.py` to route based on model selection
5. Document the new model support in `docs/`

### Adding Authentication Methods
1. Create a new authenticator class with `get_token()` method
2. Follow the pattern in `auth.py` (singleton instance)
3. Support both sync and async token refresh if needed
4. Add comprehensive error handling for auth failures
5. Never cache tokens in files (use in-memory only)

## Code Style Enforcement

Use `black` for formatting and `ruff` for linting:
```bash
black gateway/ tests/
ruff check gateway/ tests/
```

Pre-commit hooks are recommended but not required.

## Future Enhancements (Keep in Mind)

- Streaming response support for chat completions
- Model routing layer (switch between Azure/OpenAI/local models)
- Plugin system for custom pre/post-processing
- Admin API for usage tracking and token management
- OpenTelemetry or Prometheus metrics
- Request/response logging with PII masking

## When in Doubt

- Refer to `gateway/README.dev.md` for MVP requirements
- Check `meta/` directory for project philosophy and ethics
- Maintain the "thought recording" mindset: document decisions
- Prioritize security and extensibility over quick wins
