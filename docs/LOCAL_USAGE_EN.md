# YuiGateway Local Usage Guide

YuiGateway is a local proxy that securely connects to Azure OpenAI using Entra ID (Azure AD) authentication. This guide provides detailed instructions from local setup to actual usage.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup Instructions](#setup-instructions)
3. [Configuration](#configuration)
4. [Starting the Application](#starting-the-application)
5. [Usage](#usage)
6. [Running Tests](#running-tests)
7. [Troubleshooting](#troubleshooting)
8. [Development and Customization](#development-and-customization)

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

1. **Azure OpenAI Resource**
   - Azure OpenAI Service resource created in Azure Portal
   - At least one model deployed (e.g., gpt-4, gpt-35-turbo)

2. **Entra ID App Registration**
   - Application registered in Azure Portal "App registrations"
   - Client ID and Client Secret generated
   - Following permissions granted:
     - `Cognitive Services User` role (on Azure OpenAI resource)

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

### 3. Configuration

```bash
# Copy template
cp .env.template .env
```

Edit the `.env` file with your Azure credentials:

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
bash scripts/start_local.sh
```

### Method 2: Direct Start

```bash
# Using Poetry
poetry run uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000

# Using pip
uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000
```

Successful startup logs:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [xxxxx] using WatchFiles
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Usage

### 1. Health Check

Verify the application is running:

```bash
curl http://localhost:8000/health
```

**Expected response:**
```json
{
  "status": "healthy"
}
```

### 2. Get Service Information

```bash
curl http://localhost:8000/
```

**Expected response:**
```json
{
  "service": "YuiGateway",
  "version": "0.1.0",
  "description": "Entra ID-based local proxy to Azure OpenAI",
  "endpoints": ["/v1/chat/completions"]
}
```

### 3. Chat Completion Request

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
    "max_tokens": 100
  }'
```

**Note:** The `model` field should specify the **deployment name** in Azure OpenAI.

**Example response:**
```json
{
  "id": "chatcmpl-8xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 20,
    "completion_tokens": 10,
    "total_tokens": 30
  }
}
```

#### Using Python

##### Standard openai library (v0.x)

```python
import openai

# Set YuiGateway as base URL
openai.api_base = "http://localhost:8000/v1"
openai.api_key = "dummy"  # Any value works as auth is via Entra ID

# Chat completion request
response = openai.ChatCompletion.create(
    model="gpt-4",  # Azure OpenAI deployment name
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python."}
    ],
    temperature=0.7,
    max_tokens=200
)

print(response.choices[0].message.content)
```

##### New openai library (v1.x)

```python
from openai import OpenAI

# Initialize client
client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"  # Any value works
)

# Chat completion request
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me about Python."}
    ],
    temperature=0.7,
    max_tokens=200
)

print(response.choices[0].message.content)
```

##### Using httpx (low-level API)

```python
import httpx
import asyncio

async def chat():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [
                    {"role": "user", "content": "Hello!"}
                ]
            }
        )
        return response.json()

result = asyncio.run(chat())
print(result["choices"][0]["message"]["content"])
```

### 4. Parameter Reference

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `model` | string | ✅ | - | Azure OpenAI deployment name |
| `messages` | array | ✅ | - | Array of messages with role and content |
| `temperature` | float | ❌ | 1.0 | Controls randomness (0.0-2.0) |
| `max_tokens` | integer | ❌ | null | Maximum tokens to generate |
| `top_p` | float | ❌ | 1.0 | Nucleus sampling threshold (0.0-1.0) |
| `n` | integer | ❌ | 1 | Number of completions to generate |
| `stream` | boolean | ❌ | false | Streaming response (not implemented) |
| `presence_penalty` | float | ❌ | 0.0 | Encourages new topics (-2.0-2.0) |
| `frequency_penalty` | float | ❌ | 0.0 | Discourages repetition (-2.0-2.0) |

---

## Running Tests

### Run All Tests

```bash
# Using Poetry
poetry run pytest

# Or using pip
pytest
```

### Run Tests with Coverage

```bash
poetry run pytest --cov=gateway --cov-report=html
```

Coverage report is generated in `htmlcov/index.html`.

### Run Specific Test Files

```bash
pytest tests/test_routes.py
pytest tests/test_auth.py
pytest tests/test_azure_proxy.py
pytest tests/test_settings.py
```

### Run with Verbose Output

```bash
pytest -v -s
```

### Use Test Markers

```bash
# Run unit tests only
pytest -m unit

# Skip slow tests
pytest -m "not slow"
```

---

## Troubleshooting

### Issue 1: Token Acquisition Error

**Error example:**
```
ERROR: Token acquisition failed: AADSTS700016: Application with identifier 'xxx' was not found
```

**Solution:**
1. Verify `TENANT_ID` is correct
2. Verify `CLIENT_ID` is correct
3. Check that app is properly registered in Azure Portal
4. Verify the app hasn't been deleted

---

### Issue 2: Permission Error

**Error example:**
```
ERROR: 401 Unauthorized
```

**Solution:**
1. Open Azure OpenAI resource in Azure Portal
2. Go to "Access control (IAM)" → "Add role assignment"
3. Select "Cognitive Services User" role
4. Add your registered application

---

### Issue 3: Endpoint Connection Error

**Error example:**
```
ERROR: Failed to connect to Azure OpenAI endpoint
```

**Solution:**
1. Verify `AZURE_OPENAI_ENDPOINT` is correct (no trailing slash needed)
2. Ensure endpoint starts with `https://`
3. Check network connectivity
4. Verify firewall or proxy settings

---

### Issue 4: Deployment Not Found

**Error example:**
```
ERROR: 404 Not Found - The API deployment for this resource does not exist
```

**Solution:**
1. Open Azure OpenAI resource in Azure Portal
2. Check "Model deployments" for deployed models
3. Use correct deployment name in `model` field
   - ❌ `"model": "gpt-4"` (model name)
   - ✅ `"model": "my-gpt4-deployment"` (deployment name)

---

### Issue 5: .env File Not Loading

**Solution:**
1. Verify `.env` file exists in project root
   ```bash
   ls -la .env
   ```
2. Ensure filename is exactly `.env` (not `.env.template`)
3. Try setting environment variables directly:
   ```bash
   export TENANT_ID="your-tenant-id"
   export CLIENT_ID="your-client-id"
   export CLIENT_SECRET="your-client-secret"
   export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
   ```

---

### Issue 6: Port 8000 Already in Use

**Error example:**
```
ERROR: [Errno 48] Address already in use
```

**Solution:**
1. Use a different port:
   ```bash
   uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8001
   ```
2. Or stop the existing process:
   ```bash
   # Find process using the port
   lsof -i :8000
   # Stop the process
   kill -9 <PID>
   ```

---

## Development and Customization

### Code Formatting

```bash
# Format with Black
poetry run black gateway/ tests/

# Lint with Ruff
poetry run ruff check gateway/ tests/
```

### Change Log Level

In `.env` file:
```env
LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR
```

Or with environment variable:
```bash
LOG_LEVEL=DEBUG uvicorn gateway.routes:app --reload
```

### Change Timeout

Adjust timeout in `gateway/azure_proxy.py` in `AzureOpenAIProxy.__init__`:
```python
self.client = httpx.AsyncClient(timeout=180.0)  # Change to 180 seconds
```

### Change API Version

Update API version in `chat_completion` method in `gateway/azure_proxy.py`:
```python
params = {
    "api-version": "2024-08-01-preview"  # Use newer version
}
```

### Add Custom Endpoints

Add new endpoints in `gateway/routes.py`:
```python
@app.get("/v1/models")
async def list_models():
    """Return list of available models"""
    return {
        "object": "list",
        "data": [
            {"id": "gpt-4", "object": "model"},
            {"id": "gpt-35-turbo", "object": "model"}
        ]
    }
```

---

## Security Best Practices

1. **Secret Management**
   - Don't commit `.env` file to Git (already in `.gitignore`)
   - Use environment variables or Azure Key Vault in production

2. **Network Security**
   - Use `--host 127.0.0.1` in production for localhost-only access
   - Use reverse proxy (nginx, etc.) to enable HTTPS

3. **Token Caching**
   - MSAL caches tokens in memory only
   - No filesystem writes

4. **Logging**
   - Don't log tokens or credentials
   - Use `LOG_LEVEL=INFO` in production (avoid DEBUG)

---

## FAQ

### Q1: Is streaming response supported?

A: Not currently implemented. Planned for future versions.

### Q2: Can I connect to multiple Azure OpenAI resources?

A: Currently supports single endpoint only. For multiple resources, run multiple YuiGateway instances on different ports.

### Q3: Is API key-based authentication supported?

A: No, YuiGateway only supports Entra ID authentication. This is by design to avoid exposing API keys.

### Q4: Can I run it in Docker?

A: Yes, a `Dockerfile` is included:
```bash
docker build -t yui-gateway .
docker run -p 8000:8000 --env-file .env yui-gateway
```

### Q5: Can I use clients other than OpenAI library?

A: Yes, any HTTP client can be used as it provides an OpenAI-compatible API.

---

## Support and Feedback

- **GitHub Issues**: https://github.com/vemikrs/yui-gateway/issues
- **Documentation**: `docs/` directory
- **Development Guide**: `gateway/README.dev.md`

---

## Next Steps

- Read [Architecture Overview](./overview.md)
- Check [Use Cases](./use-cases.md)
- Learn customization in [Development Guide](../gateway/README.dev.md)

---

**Last updated:** 2024-11-04
