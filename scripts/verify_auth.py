#!/usr/bin/env python3
"""Verify Entra (Azure AD) client-credential auth for YuiGateway.

This script:
- Loads settings from `.env`
- Acquires an access token via MSAL
- Optionally runs a minimal chat completion to Azure OpenAI when `--deployment` is provided

Exit codes:
- 0: Success
- 2: Missing or invalid configuration
- 3: Token acquisition failed
- 4: Test request to Azure OpenAI failed

Notes:
- This script never prints the raw token.
"""

from __future__ import annotations

import argparse
import sys

from gateway.auth import get_authenticator
from gateway.azure_proxy import AzureOpenAIProxy
from gateway.settings import settings


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify Entra authentication and optional test request")
    p.add_argument("--deployment", help="Azure OpenAI deployment name to test a minimal request")
    p.add_argument("--max-tokens", type=int, default=8)
    p.add_argument("--temperature", type=float, default=0.0)
    return p.parse_args()


def validate_settings() -> list[str]:
    errors = []
    if not settings.tenant_id:
        errors.append("TENANT_ID is missing")
    if not settings.client_id:
        errors.append("CLIENT_ID is missing")
    if not settings.client_secret:
        errors.append("CLIENT_SECRET is missing")
    if not settings.azure_openai_endpoint:
        errors.append("AZURE_OPENAI_ENDPOINT is missing")
    return errors


async def main(argv: list[str]) -> int:
    args = parse_args()

    errs = validate_settings()
    if errs:
        print("Invalid configuration:")
        for e in errs:
            print(f" - {e}")
        return 2

    # Acquire token
    try:
        token = get_authenticator().get_token()
        # Do not print token; only confirm success
        print("OK: Entra token acquisition succeeded.")
    except Exception as e:
        print(f"ERROR: Token acquisition failed: {e}")
        return 3

    if not args.deployment:
        return 0

    # Optional minimal request
    try:
        proxy = AzureOpenAIProxy()
        payload = {
            "model": args.deployment,
            "messages": [{"role": "user", "content": "ping"}],
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
        }
        resp = await proxy.chat_completion(payload)
        # Summarize success without leaking content
        choices = resp.get("choices", [])
        print(f"OK: Azure OpenAI request succeeded (choices={len(choices)}).")
        await proxy.close()
        return 0
    except Exception as e:
        print(f"ERROR: Azure OpenAI request failed: {e}")
        return 4


if __name__ == "__main__":
    try:
        import asyncio

        sys.exit(asyncio.run(main(sys.argv[1:])))
    except KeyboardInterrupt:
        sys.exit(130)
