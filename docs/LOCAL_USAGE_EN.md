# YuiGateway Local Usage Guide

YuiGateway is a local proxy that securely connects to Azure OpenAI using Entra ID (Azure AD) authentication. This guide provides detailed instructions from local setup to actual usage.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Auto-Provisioning)](#quick-start-auto-provisioning)
3. [Setup Instructions](#setup-instructions)
4. [Configuration File Preparation](#configuration-file-preparation)
5. [Starting the Application](#starting-the-application)
6. [Usage Examples](#usage-examples)
7. [VS Code Integration](#vs-code-integration)
8. [Running Tests](#running-tests)
9. [Troubleshooting](#troubleshooting)
10. [Development and Customization](#development-and-customization)

---

## Prerequisites

### Required Software

- **Python 3.10 or higher**
  ```bash
  python --version  # Verify Python 3.10.0 or higher
  ```

- **Poetry** (recommended) or **pip**
  ```bash
  # Install Poetry
  curl -sSL https://install.python-poetry.org | python3 -

  # Or use pip
  pip install poetry
  ```

- **Git**
  ```bash
  git --version
  ```

### Azure Prerequisites

1. **Azure Subscription**
   - Active Azure subscription with appropriate permissions
   - Azure OpenAI Service access (may require application approval)

2. **Authentication Method** (choose one):
   - **Interactive Login** (recommended for local development)
   - **Device Code Flow** (for headless environments)
   - **Service Principal** (for CI/CD or automated scenarios)

3. **Azure OpenAI Resource & Model Deployment**
   - Azure OpenAI Service resource with deployed models
   - Compatible models: gpt-4, gpt-4-32k, gpt-35-turbo, gpt-35-turbo-16k
   - Note: Different model generations have different parameter requirements
     - Legacy models: use `max_tokens`
     - Newer models: use `max_completion_tokens`

---

## Quick Start (Auto-Provisioning)

🚀 **Fastest way to get started**

YuiGateway includes an automated provisioning system that handles Azure resource discovery and configuration:

```bash
# Clone and navigate
git clone https://github.com/vemikrs/yui-gateway.git
cd yui-gateway

# Install dependencies
poetry install && poetry shell

# Auto-provision and start (with interactive login)
python scripts/provision_env.py --mode interactive
# Automatically creates .env and starts the server
```

**Alternative authentication modes:**
```bash
# Device code flow (for remote/headless environments)
python scripts/provision_env.py --mode device

# CLI-based credential input
python scripts/provision_env.py --mode cli
```

**Deployment discovery:**
```bash
# List available deployments across subscriptions
python scripts/list_deployments.py
# Shows: Resource names, model versions, deployment status
```

**VS Code Integration:**
- Open the project in VS Code
- Use built-in tasks: `Ctrl+Shift+P` → "Tasks: Run Task"
- Available: Start Server, Run Tests, Format Code, etc.

---

## Setup Instructions

### 1. Clone the Repository

```bash
# Clone the repository
git clone https://github.com/vemikrs/yui-gateway.git
cd yui-gateway
```

### 2. Install Dependencies

**Using Poetry (recommended):**

```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

**Using pip:**

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Linux/Mac:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn[standard] msal httpx pydantic-settings python-dotenv
```

---

## Configuration File Preparation

### 🎯 Recommended Method: Auto-Provisioning

The **automated provisioning system** handles all configuration automatically:

```bash
# Automatic setup with interactive login
python scripts/provision_env.py --mode interactive

# Alternative: Device code flow
python scripts/provision_env.py --mode device

# The script will:
# 1. Authenticate with Azure
# 2. Discover available resources
# 3. Create optimized .env configuration
# 4. Start the server automatically
```

**Benefits of auto-provisioning:**
- ✅ No manual credential management
- 🔍 Automatic resource discovery
- 🚀 Immediate startup after configuration
- 🔄 Easy switching between environments

### Alternative Method: Manual Configuration

💡 **Use this method when auto-provisioning is restricted by organizational policies**

**Step 1: Copy template**
```bash
cp .env.template .env
```

**Step 2: Edit the .env file**
```env
# Azure AD (Entra ID) authentication
TENANT_ID=your-tenant-id-here
CLIENT_ID=your-client-id-here
CLIENT_SECRET=your-client-secret-here

# Scope (usually keep as is)
SCOPE=https://cognitiveservices.azure.com/.default

# Azure OpenAI endpoint
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com
```

#### How to Obtain Credentials

**Get TENANT_ID:**
1. Log in to Azure Portal
2. Open "Azure Active Directory" (or "Microsoft Entra ID")
3. Copy "Tenant ID" from "Overview"

**Get CLIENT_ID and CLIENT_SECRET:**
1. Open "App registrations" in Azure Portal
2. Select your registered application
3. Copy "Application (client) ID" from "Overview" → `CLIENT_ID`
4. Go to "Certificates & secrets" → "New client secret" to create a secret
5. Copy the "Value" of the created secret → `CLIENT_SECRET`
   - ⚠️ The secret is only displayed once, so make sure to copy it

**Get AZURE_OPENAI_ENDPOINT:**
1. Open your Azure OpenAI resource in Azure Portal
2. Copy the "Endpoint" from "Keys and Endpoint" section
3. Example: `https://my-resource.openai.azure.com`

---

## Starting the Application

### Method 1: Using Script

```bash
# Allow auto-provisioning if .env doesn't exist
AUTO_PROVISION=1 bash scripts/start_local.sh

# Or start normally with existing .env
bash scripts/start_local.sh
```

### Method 2: VS Code Tasks

Open in VS Code and use integrated tasks:
```
Ctrl+Shift+P → "Tasks: Run Task" → "Start YuiGateway Server"
```

### Method 3: Direct Start

```bash
# Using Poetry
poetry run uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000

# Using virtual environment
.venv/bin/uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000
```

### Successful Startup Verification

**Startup logs:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Application startup complete.
```

**Health check:**
```bash
curl http://localhost:8000/health
# → {"status": "healthy"}
```

---

## Usage Examples

### 1. Basic Chat Completion

#### Using curl

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ],
    "temperature": 0.7,
    "max_completion_tokens": 100
  }'
```

#### Model Parameter Compatibility

⚠️ **Important:** Different model generations use different token limit parameters:

```bash
# For newer models (gpt-4-turbo and later)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [...],
    "max_completion_tokens": 100
  }'

# For legacy models (gpt-35-turbo, older gpt-4)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-35-turbo",
    "messages": [...],
    "max_tokens": 100
  }'
```

### 2. Python Integration

#### OpenAI Library v1.x (Recommended)

```python
from openai import OpenAI

# Initialize client
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # Any value works with Entra ID auth
)

# Chat completion with proper parameter handling
response = client.chat.completions.create(
    model="gpt-4",  # Your Azure deployment name
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python."}
    ],
    temperature=0.7,
    max_completion_tokens=200  # Use this for newer models
)

print(response.choices[0].message.content)
```

#### Legacy OpenAI Library (v0.x)

```python
import openai

# Set YuiGateway as base URL
openai.api_base = "http://localhost:8000/v1"
openai.api_key = "dummy"  # Any value works

response = openai.ChatCompletion.create(
    model="gpt-35-turbo",  # Azure deployment name
    messages=[
        {"role": "user", "content": "Hello!"}
    ],
    max_tokens=100  # Use this for legacy models
)

print(response.choices[0].message.content)
```

### 3. Advanced Usage

#### Async HTTP Client (httpx)

```python
import httpx
import asyncio

async def chat():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello!"}],
                "max_completion_tokens": 100,
                "temperature": 0.3
            }
        )
        return response.json()

result = asyncio.run(chat())
print(result["choices"][0]["message"]["content])
```

#### Parameter Reference

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `model` | string | ✅ | Azure OpenAI deployment name |
| `messages` | array | ✅ | Conversation history |
| `max_completion_tokens` | integer | ❌ | For newer models (recommended) |
| `max_tokens` | integer | ❌ | For legacy models |
| `temperature` | float | ❌ | 0.0-2.0, controls randomness |
| `top_p` | float | ❌ | 0.0-1.0, nucleus sampling |
| `presence_penalty` | float | ❌ | -2.0-2.0, encourages new topics |
| `frequency_penalty` | float | ❌ | -2.0-2.0, discourages repetition |

---

## VS Code Integration

YuiGateway includes pre-configured VS Code tasks for seamless development:

### Available Tasks

Access via `Ctrl+Shift+P` → "Tasks: Run Task":

1. **Start YuiGateway Server** - Launch server with auto-reload
2. **Run Tests** - Execute pytest test suite
3. **Run Tests with Coverage** - Tests with coverage report
4. **Format Code (Black)** - Auto-format Python code
5. **Lint Code (Ruff)** - Check code quality
6. **Full Check** - Format + Lint + Test in sequence

### Development Workflow

```bash
# 1. Open in VS Code
code /path/to/yui-gateway

# 2. Install dependencies (if needed)
Ctrl+Shift+P → "Tasks: Run Task" → "Install Dependencies"

# 3. Start development server
Ctrl+Shift+P → "Tasks: Run Task" → "Start YuiGateway Server"

# 4. Run tests during development
Ctrl+Shift+P → "Tasks: Run Task" → "Run Tests"
```

### Task Configuration

All tasks are defined in `.vscode/tasks.json` with proper Python virtual environment integration.

---

## Running Tests

### Quick Test Execution

**VS Code Integration:**
```
Ctrl+Shift+P → "Tasks: Run Task" → "Run Tests"
```

**Command Line:**
```bash
# Basic test run
poetry run pytest tests/ -v

# With coverage report
poetry run pytest tests/ -v --cov=gateway --cov-report=html --cov-report=term

# Fast execution (parallel)
poetry run pytest tests/ -v -n auto
```

### Test Categories

YuiGateway includes **45+ comprehensive tests** covering:

- **Authentication Tests** (`test_auth.py`) - MSAL token acquisition, error handling
- **Proxy Tests** (`test_azure_proxy.py`) - Request forwarding, response handling
- **Route Tests** (`test_routes.py`) - FastAPI endpoints, validation
- **Settings Tests** (`test_settings.py`) - Configuration management

### Development Testing

```bash
# Run specific test file
pytest tests/test_routes.py -v

# Run with live output
pytest tests/ -v -s

# Run tests matching pattern
pytest tests/ -k "test_chat_completion" -v

# Skip slow integration tests
pytest tests/ -m "not slow" -v
```

### Coverage Analysis

```bash
# Generate detailed coverage
poetry run pytest tests/ --cov=gateway --cov-report=html

# View coverage in browser
open htmlcov/index.html
```

---

## Troubleshooting

### 🔍 Common Issues and Solutions

#### Issue 1: Auto-Provisioning Authentication Failed

**Error:**
```
AADSTS50020: User account 'user@domain.com' from identity provider does not exist in tenant
```

**Solutions:**
- ✅ Verify Azure subscription access permissions
- ✅ Use `--mode device` for organizational accounts
- ✅ Check tenant restrictions with IT department
- ✅ Try with personal Microsoft account if available

#### Issue 2: Model Parameter Compatibility

**Error:**
```
BadRequestError: Invalid parameter 'max_tokens' for model 'gpt-4-turbo'
```

**Solutions:**
- ✅ Use `max_completion_tokens` for newer models (gpt-4-turbo, etc.)
- ✅ Use `max_tokens` for legacy models (gpt-35-turbo, older gpt-4)
- ✅ Run `python scripts/list_deployments.py` to check model versions

#### Issue 3: Permission Denied on Azure Resource

**Error:**
```
HTTPError: 403 Forbidden - Access denied due to invalid subscription key
```

**Solutions:**
- ✅ Verify `Cognitive Services User` role assignment
- ✅ Check resource-level permissions in Azure Portal
- ✅ Ensure subscription is active and not expired
- ✅ Re-run auto-provisioning to refresh permissions

#### Issue 4: Environment Configuration Issues

**Symptoms:**
- Server starts but returns authentication errors
- Missing `.env` file after manual setup

**Solutions:**
```bash
# Regenerate configuration automatically
rm .env
python scripts/provision_env.py --mode interactive

# Validate current configuration
python -c "from gateway.settings import settings; print(settings.model_dump())"

# Check resource accessibility
python scripts/list_deployments.py
```

#### Issue 5: VS Code Task Execution Problems

**Error:**
```
The terminal process terminated with exit code: 1
```

**Solutions:**
- ✅ Ensure Poetry virtual environment is activated: `poetry shell`
- ✅ Check Python interpreter in VS Code: `Ctrl+Shift+P` → "Python: Select Interpreter"
- ✅ Reinstall dependencies: `poetry install --no-cache`
- ✅ Verify `.vscode/tasks.json` paths match your system

### 🧪 Advanced Debugging

#### Enable Debug Logging

```bash
# Set debug level in .env
echo "LOG_LEVEL=DEBUG" >> .env

# Or export temporarily
export LOG_LEVEL=DEBUG
poetry run uvicorn gateway.routes:app --reload
```

#### Check Service Health

```bash
# Test endpoint accessibility
curl -v http://localhost:8000/health

# Test Azure OpenAI connectivity
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-35-turbo","messages":[{"role":"user","content":"test"}],"max_tokens":5}'
```

#### Validate Environment

```bash
# Check all environment variables
poetry run python -c "
from gateway.settings import settings
import json
print(json.dumps(settings.model_dump(), indent=2))
"

# Test token acquisition manually
poetry run python -c "
from gateway.auth import authenticator
token = authenticator.get_token()
print('Token acquired successfully' if token else 'Token acquisition failed')
"
```
---

## Development and Customization

### 🛠️ Code Quality Tools

**Integrated VS Code Tasks:**
```
Ctrl+Shift+P → "Tasks: Run Task" → "Format Code (Black)"
Ctrl+Shift+P → "Tasks: Run Task" → "Lint Code (Ruff)"
Ctrl+Shift+P → "Tasks: Run Task" → "Full Check"
```

**Command Line:**
```bash
# Format code
poetry run black gateway/ tests/

# Lint and auto-fix
poetry run ruff check --fix gateway/ tests/

# Type checking (if mypy installed)
poetry run mypy gateway/
```

### ⚙️ Configuration Customization

#### Change Log Level
```bash
# In .env file
echo "LOG_LEVEL=DEBUG" >> .env

# Or temporarily
LOG_LEVEL=DEBUG poetry run uvicorn gateway.routes:app --reload
```

#### Adjust Timeout Settings
Edit `gateway/azure_proxy.py`:
```python
self.client = httpx.AsyncClient(timeout=300.0)  # 5 minutes
```

#### Update Azure API Version
Modify `gateway/azure_proxy.py`:
```python
params = {
    "api-version": "2024-08-01-preview"  # Latest version
}
```

### 🔧 Extension Development

#### Add New Endpoints
In `gateway/routes.py`:
```python
@app.get("/v1/models")
async def list_models():
    """List available models"""
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4", "object": "model", "owned_by": "azure"},
            {"id": "gpt-35-turbo", "object": "model", "owned_by": "azure"}
        ]
    }
```

#### Add Custom Middleware
```python
from fastapi import Request, Response
import time

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response
```

### 🔒 Security Best Practices

1. **Environment Security**
   - ✅ Never commit `.env` files (already in `.gitignore`)
   - ✅ Use Azure Key Vault for production secrets
   - ✅ Rotate client secrets regularly

2. **Network Security**
   - ✅ Use `--host 127.0.0.1` for localhost-only access
   - ✅ Implement reverse proxy with HTTPS in production
   - ✅ Configure appropriate CORS settings

3. **Monitoring and Logging**
   - ✅ Use structured logging in production
   - ✅ Never log tokens or sensitive data
   - ✅ Set `LOG_LEVEL=INFO` in production

### 🐳 Docker Deployment

```bash
# Build image
docker build -t yui-gateway .

# Run with environment file
docker run -p 8000:8000 --env-file .env yui-gateway

# Run with Docker Compose
docker-compose up -d
```

### 🧪 Testing and CI/CD

#### Local Testing
```bash
# Full test suite
poetry run pytest tests/ -v --cov=gateway

# Specific test categories
pytest tests/test_auth.py -v
pytest tests/test_routes.py::test_chat_completion -v

# Performance testing
pytest tests/ -v --benchmark-only
```

#### Pre-commit Setup
```bash
# Install pre-commit hooks
poetry run pre-commit install

# Run hooks manually
poetry run pre-commit run --all-files
```

---

## FAQ & Support

### ❓ Frequently Asked Questions

**Q: Is streaming response supported?**
A: Currently in development. Basic streaming infrastructure is planned for v0.2.0.

**Q: Can I connect to multiple Azure OpenAI resources?**
A: Single endpoint per instance. Run multiple YuiGateway instances on different ports for multiple resources.

**Q: Is OpenAI API key authentication supported?**
A: No, by design. YuiGateway exclusively uses Entra ID to avoid key exposure risks.

**Q: Can I use it with other language models?**
A: Architecture supports model switching. Azure OpenAI is the current implementation.

**Q: How do I report issues or contribute?**
A: Use GitHub Issues for bug reports, feature requests, and contributions.

### 📚 Additional Resources

- **Architecture Deep Dive**: [docs/overview.md](./overview.md)
- **Real-world Examples**: [docs/use-cases.md](./use-cases.md)
- **Developer Documentation**: [gateway/README.dev.md](../gateway/README.dev.md)
- **GitHub Repository**: https://github.com/vemikrs/yui-gateway

### 🤝 Getting Help

- **Issues & Bugs**: GitHub Issues tracker
- **Feature Requests**: GitHub Discussions
- **Documentation**: Built-in `docs/` directory
- **Code Examples**: `tests/` directory contains working examples

---

**Last updated:** 2024-12-19
