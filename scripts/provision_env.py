#!/usr/bin/env python3
"""Provision Azure resources and generate .env automatically for YuiGateway.

This script performs the following with Azure SDKs and Microsoft Graph:
- Discover tenant, subscriptions, and Azure OpenAI resource endpoint
- Create an App registration + Client secret
- Ensure Service Principal exists
- Assign "Cognitive Services User" role on the selected Azure OpenAI resource
- Write `.env` with TENANT_ID, CLIENT_ID, CLIENT_SECRET, SCOPE, AZURE_OPENAI_ENDPOINT

Requirements:
- `az login` or otherwise usable credentials for `DefaultAzureCredential`
- Permissions to create application/service principal in Entra ID
- RBAC privileges to assign roles on the Azure OpenAI resource

Usage (auto-discover first OpenAI resource):
    python scripts/provision_env.py

Usage (explicit selection):
    python scripts/provision_env.py \
      --subscription-id <SUB_ID> \
      --resource-group <RG> \
      --account-name <COGNITIVE_ACCOUNT_NAME> \
      --app-name YuiGateway-App
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from uuid import uuid4

import httpx
from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.models import RoleAssignmentCreateParameters
from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient
from azure.mgmt.resource.subscriptions import SubscriptionClient


ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


@dataclass
class OpenAIAccount:
    subscription_id: str
    resource_group: str
    name: str
    id: str
    endpoint: str


def get_credential() -> DefaultAzureCredential:
    # DefaultAzureCredential will use Azure CLI token when available (recommended for dev)
    return DefaultAzureCredential(exclude_interactive_browser_credential=True)


async def graph_request(
    client: httpx.AsyncClient, method: str, url: str, token: str, **kwargs
):
    headers = kwargs.pop("headers", {})
    headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return await client.request(method, url, headers=headers, **kwargs)


def get_tenant_id_from_token(token: str) -> Optional[str]:
    # Graph /organization is authoritative; token parsing is avoided for simplicity
    return None


async def get_tenant_id(credential: DefaultAzureCredential) -> str:
    token = (await credential.get_token("https://graph.microsoft.com/.default")).token
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await graph_request(client, "GET", "https://graph.microsoft.com/v1.0/organization", token)
        resp.raise_for_status()
        data = resp.json()
        orgs = data.get("value", [])
        if not orgs:
            raise RuntimeError("テナント情報を取得できませんでした")
        return orgs[0]["id"]


def list_openai_accounts(credential: DefaultAzureCredential) -> List[OpenAIAccount]:
    accounts: List[OpenAIAccount] = []
    sub_client = SubscriptionClient(credential)
    for sub in sub_client.subscriptions.list():
        sub_id = sub.subscription_id
        cog_client = CognitiveServicesManagementClient(credential, sub_id)
        for acct in cog_client.accounts.list():
            try:
                kind = getattr(acct, "kind", "") or ""
                # Azure OpenAI accounts have kind "OpenAI"
                if kind.lower() != "openai":
                    continue
                rg = acct.id.split("/resourceGroups/")[1].split("/")[0]
                accounts.append(
                    OpenAIAccount(
                        subscription_id=sub_id,
                        resource_group=rg,
                        name=acct.name,
                        id=acct.id,
                        endpoint=acct.properties.endpoint,
                    )
                )
            except Exception:
                continue
    return accounts


def resolve_account(
    credential: DefaultAzureCredential,
    subscription_id: Optional[str],
    resource_group: Optional[str],
    account_name: Optional[str],
) -> OpenAIAccount:
    if subscription_id and resource_group and account_name:
        cog_client = CognitiveServicesManagementClient(credential, subscription_id)
        acct = cog_client.accounts.get(resource_group, account_name)
        return OpenAIAccount(
            subscription_id=subscription_id,
            resource_group=resource_group,
            name=account_name,
            id=acct.id,
            endpoint=acct.properties.endpoint,
        )

    accounts = list_openai_accounts(credential)
    if not accounts:
        raise RuntimeError("Azure OpenAI リソースが見つかりません。--subscription-id/--resource-group/--account-name を指定してください。")
    # Prefer single; if multiple, pick the first for non-interactive simplicity
    return accounts[0]


async def ensure_application(
    credential: DefaultAzureCredential, display_name: str
) -> Tuple[str, str, str]:
    """Ensure an App Registration exists and has a client secret.

    Returns tuple: (application_id, client_id, client_secret)
    - application_id: Graph object id
    - client_id: App ID (aka application (client) ID)
    - client_secret: Newly created secret value
    """
    token = (await credential.get_token("https://graph.microsoft.com/.default")).token
    async with httpx.AsyncClient(timeout=60) as client:
        # Try to find existing application by displayName
        url = "https://graph.microsoft.com/v1.0/applications?$select=id,appId,displayName&$filter=" \
              f"displayName eq '{display_name.replace("'", "''")}'"
        resp = await graph_request(client, "GET", url, token)
        resp.raise_for_status()
        items = resp.json().get("value", [])
        if items:
            app = items[0]
        else:
            # Create application
            payload = {"displayName": display_name}
            resp = await graph_request(client, "POST", "https://graph.microsoft.com/v1.0/applications", token, json=payload)
            resp.raise_for_status()
            app = resp.json()

        app_obj_id = app["id"]
        client_id = app["appId"]

        # Create client secret
        pwd_payload = {"passwordCredential": {"displayName": "yui-gateway-secret"}}
        resp = await graph_request(
            client, "POST", f"https://graph.microsoft.com/v1.0/applications/{app_obj_id}/addPassword", token, json=pwd_payload
        )
        resp.raise_for_status()
        secret = resp.json().get("secretText")
        if not secret:
            raise RuntimeError("クライアントシークレットの生成に失敗しました")

        return app_obj_id, client_id, secret


async def ensure_service_principal(
    credential: DefaultAzureCredential, client_id: str
) -> str:
    """Ensure Service Principal exists for the application; returns SP object id."""
    token = (await credential.get_token("https://graph.microsoft.com/.default")).token
    async with httpx.AsyncClient(timeout=60) as client:
        # Find existing
        url = (
            "https://graph.microsoft.com/v1.0/servicePrincipals?$select=id,appId&$filter="
            f"appId eq '{client_id}'"
        )
        resp = await graph_request(client, "GET", url, token)
        resp.raise_for_status()
        items = resp.json().get("value", [])
        if items:
            return items[0]["id"]

        # Create
        payload = {"appId": client_id}
        resp = await graph_request(client, "POST", "https://graph.microsoft.com/v1.0/servicePrincipals", token, json=payload)
        resp.raise_for_status()
        return resp.json()["id"]


def assign_cog_user_role(
    credential: DefaultAzureCredential,
    subscription_id: str,
    resource_scope: str,
    principal_object_id: str,
) -> None:
    auth = AuthorizationManagementClient(credential, subscription_id)
    # Find role definition for "Cognitive Services User"
    defs = auth.role_definitions.list(resource_scope, filter="roleName eq 'Cognitive Services User'")
    role_def_id = None
    for d in defs:
        role_def_id = d.id
        break
    if not role_def_id:
        raise RuntimeError("'Cognitive Services User' ロール定義が見つかりません")

    params = RoleAssignmentCreateParameters(role_definition_id=role_def_id, principal_id=principal_object_id)
    name = str(uuid4())
    try:
        auth.role_assignments.create(scope=resource_scope, role_assignment_name=name, parameters=params)
    except Exception as e:
        # Might already exist; attempt to ignore duplicates
        message = str(e)
        if "RoleAssignmentExists" not in message:
            raise


def update_env(env_path: Path, values: dict) -> None:
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    mapping = {k: str(v) for k, v in values.items()}
    keys = set(mapping.keys())
    out: List[str] = []
    for line in lines:
        if not line or line.strip().startswith("#") or "=" not in line:
            out.append(line)
            continue
        k, _ = line.split("=", 1)
        if k in mapping:
            out.append(f"{k}={mapping[k]}")
            keys.remove(k)
        else:
            out.append(line)
    if keys:
        if out and out[-1] != "":
            out.append("")
        out.append("# --- Added by scripts/provision_env.py ---")
        for k in keys:
            out.append(f"{k}={mapping[k]}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Provision Azure + generate .env for YuiGateway")
    p.add_argument("--subscription-id")
    p.add_argument("--resource-group")
    p.add_argument("--account-name")
    p.add_argument("--app-name", default="YuiGateway-App")
    p.add_argument("--scope", default="https://cognitiveservices.azure.com/.default")
    return p.parse_args(argv)


async def main(argv: List[str]) -> int:
    args = parse_args(argv)
    cred = get_credential()

    # Discover tenant and OpenAI endpoint
    tenant_id = await get_tenant_id(cred)
    acct = resolve_account(cred, args.subscription_id, args.resource_group, args.account_name)

    # Create App + Secret + SP
    app_obj_id, client_id, client_secret = await ensure_application(cred, args.app_name)
    sp_obj_id = await ensure_service_principal(cred, client_id)

    # Assign RBAC
    assign_cog_user_role(cred, acct.subscription_id, acct.id, sp_obj_id)

    # Write .env
    update_env(
        ENV_FILE,
        {
            "TENANT_ID": tenant_id,
            "CLIENT_ID": client_id,
            "CLIENT_SECRET": client_secret,
            "SCOPE": args.scope,
            "AZURE_OPENAI_ENDPOINT": acct.endpoint,
        },
    )

    print(".env を生成/更新しました。内容:")
    print(f" - TENANT_ID={tenant_id}")
    print(f" - CLIENT_ID={client_id}")
    print(f" - CLIENT_SECRET=***{client_secret[-4:]}")
    print(f" - SCOPE={args.scope}")
    print(f" - AZURE_OPENAI_ENDPOINT={acct.endpoint}")
    print("完了しました。")
    return 0


if __name__ == "__main__":
    try:
        import asyncio

        sys.exit(asyncio.run(main(sys.argv[1:])))
    except KeyboardInterrupt:
        print("中断されました。", file=sys.stderr)
        sys.exit(130)
