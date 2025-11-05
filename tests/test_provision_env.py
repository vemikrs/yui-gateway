"""Tests for scripts/provision_env.py

These tests avoid real Azure/Graph calls by mocking all external interactions.
Focus is on:
- update_env: correct writing/merging behavior
- main: end-to-end flow with mocks writes a complete .env
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest


def read_env_map(path: Path) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k] = v
    return data


def test_update_env_writes_and_preserves(tmp_path: Path):
    from scripts.provision_env import update_env

    env = tmp_path / ".env"
    env.write_text("TENANT_ID=old-tenant\nEXTRA=keep\n", encoding="utf-8")

    update_env(
        env,
        {
            "TENANT_ID": "00000000-0000-0000-0000-000000000000",
            "CLIENT_ID": "11111111-1111-1111-1111-111111111111",
            "CLIENT_SECRET": "secret",
            "SCOPE": "https://cognitiveservices.azure.com/.default",
            "AZURE_OPENAI_ENDPOINT": "https://res.openai.azure.com",
        },
    )

    m = read_env_map(env)
    assert m["TENANT_ID"] == "00000000-0000-0000-0000-000000000000"
    assert m["CLIENT_ID"] == "11111111-1111-1111-1111-111111111111"
    assert m["CLIENT_SECRET"] == "secret"
    assert m["SCOPE"] == "https://cognitiveservices.azure.com/.default"
    assert m["AZURE_OPENAI_ENDPOINT"] == "https://res.openai.azure.com"
    # Unrelated keys should be preserved
    assert m["EXTRA"] == "keep"


@pytest.mark.asyncio
async def test_main_generates_env_with_mocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import scripts.provision_env as pe

    # Redirect ENV_FILE to tmp
    env_file = tmp_path / ".env"
    monkeypatch.setattr(pe, "ENV_FILE", env_file, raising=True)

    # Short-circuit all external calls
    class DummyCred:  # noqa: D401 - trivial stub
        """Dummy credential object"""

        pass

    monkeypatch.setattr(pe, "get_credential", lambda: DummyCred(), raising=True)
    async def _fake_get_tenant_id(_):
        return "00000000-0000-0000-0000-000000000000"

    monkeypatch.setattr(pe, "get_tenant_id", _fake_get_tenant_id, raising=True)

    # Fake account
    acct = pe.OpenAIAccount(
        subscription_id="sub",
        resource_group="rg",
        name="acct",
        id="/subscriptions/sub/resourceGroups/rg/providers/Microsoft.CognitiveServices/accounts/acct",
        endpoint="https://res.openai.azure.com",
    )
    monkeypatch.setattr(pe, "resolve_account", lambda *a, **k: acct, raising=True)

    # App + SP + RBAC
    async def _fake_ensure_application(*_a, **_k):
        return ("obj", "11111111-1111-1111-1111-111111111111", "s3cr3t")

    async def _fake_ensure_sp(*_a, **_k):
        return "spobj"

    monkeypatch.setattr(pe, "ensure_application", _fake_ensure_application, raising=True)
    monkeypatch.setattr(pe, "ensure_service_principal", _fake_ensure_sp, raising=True)
    monkeypatch.setattr(pe, "assign_cog_user_role", lambda *a, **k: None, raising=True)

    # Run
    rc = await pe.main([])
    assert rc == 0

    # Verify .env contents
    m = read_env_map(env_file)
    assert m["TENANT_ID"] == "00000000-0000-0000-0000-000000000000"
    assert m["CLIENT_ID"] == "11111111-1111-1111-1111-111111111111"
    assert m["CLIENT_SECRET"] == "s3cr3t"
    assert m["SCOPE"] == "https://cognitiveservices.azure.com/.default"
    assert m["AZURE_OPENAI_ENDPOINT"] == "https://res.openai.azure.com"
