#!/usr/bin/env python3
"""Interactive/non-interactive .env configurator for YuiGateway.

This script automates the steps in docs/LOCAL_USAGE.md (設定ファイルの準備):
- Ensure `.env` exists (copy from `.env.template` if needed)
- Collect Azure credentials (interactive prompts or CLI flags)
- Validate values and write them into `.env`

Usage (interactive):
    python scripts/setup_env.py

Usage (non-interactive):
    python scripts/setup_env.py \
      --tenant-id "<TENANT_ID>" \
      --client-id "<CLIENT_ID>" \
      --client-secret "<CLIENT_SECRET>" \
      --endpoint "https://<resource>.openai.azure.com"

Notes:
- The default SCOPE is https://cognitiveservices.azure.com/.default
- Existing `.env` will be updated in-place; a backup `.env.bak` is created unless --no-backup.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
ENV_TEMPLATE = ROOT / ".env.template"


REQUIRED_KEYS = [
    "TENANT_ID",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "SCOPE",
    "AZURE_OPENAI_ENDPOINT",
]


def _is_uuid_like(value: str) -> bool:
    try:
        import uuid

        uuid.UUID(value)
        return True
    except Exception:
        return False


def _is_valid_endpoint(value: str) -> bool:
    from urllib.parse import urlparse

    try:
        parsed = urlparse(value)
        if parsed.scheme != "https":
            return False
        host = (parsed.hostname or "").lower()
        return host.endswith(".openai.azure.com")
    except Exception:
        return False


def _mask(value: str, show: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= show:
        return "*" * len(value)
    return f"{'*' * (len(value) - show)}{value[-show:]}"


def _read_env_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _write_env_lines(path: Path, lines: List[str]) -> None:
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")


def _update_env_lines(lines: List[str], updates: Dict[str, str]) -> List[str]:
    key_pattern = re.compile(r"^([A-Z0-9_]+)=.*$")
    present = set()
    new_lines: List[str] = []
    for line in lines:
        m = key_pattern.match(line)
        if m:
            key = m.group(1)
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                present.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append missing keys at the end, grouped under a marker
    missing = [k for k in updates.keys() if k not in present]
    if missing:
        new_lines.append("")
        new_lines.append("# --- Added by scripts/setup_env.py ---")
        for k in missing:
            new_lines.append(f"{k}={updates[k]}")

    return new_lines


def _maybe_copy_template(no_backup: bool) -> None:
    if ENV_FILE.exists():
        return
    if not ENV_TEMPLATE.exists():
        # Create a minimal template if missing
        minimal = (
            "# Auto-generated minimal .env template\n"
            "TENANT_ID=\nCLIENT_ID=\nCLIENT_SECRET=\n"
            "SCOPE=https://cognitiveservices.azure.com/.default\n"
            "AZURE_OPENAI_ENDPOINT=\n"
        )
        ENV_FILE.write_text(minimal, encoding="utf-8")
        return
    shutil.copy2(ENV_TEMPLATE, ENV_FILE)


def _backup_env(no_backup: bool) -> Optional[Path]:
    if no_backup or not ENV_FILE.exists():
        return None
    bak = ENV_FILE.with_suffix(".bak")
    shutil.copy2(ENV_FILE, bak)
    return bak


def _detect_tenant_from_azure_cli() -> Optional[str]:
    try:
        proc = subprocess.run(
            ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
            check=True,
            capture_output=True,
            text=True,
        )
        tid = proc.stdout.strip()
        return tid or None
    except Exception:
        return None


def _prompt(label: str, default: Optional[str] = None, secret: bool = False) -> str:
    prompt = f"{label}"
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    if secret:
        import getpass

        value = getpass.getpass(prompt)
    else:
        value = input(prompt)
    return value.strip() or (default or "")


def _validate(values: Dict[str, str]) -> List[str]:
    errors: List[str] = []
    if not _is_uuid_like(values.get("TENANT_ID", "")):
        errors.append("TENANT_ID は UUID 形式で入力してください")
    if not _is_uuid_like(values.get("CLIENT_ID", "")):
        errors.append("CLIENT_ID は UUID 形式で入力してください")
    if not values.get("CLIENT_SECRET"):
        errors.append("CLIENT_SECRET を入力してください")
    scope = values.get("SCOPE", "")
    if not scope:
        errors.append("SCOPE を入力してください")
    endpoint = values.get("AZURE_OPENAI_ENDPOINT", "")
    if not _is_valid_endpoint(endpoint):
        errors.append(
            "AZURE_OPENAI_ENDPOINT は https://<resource>.openai.azure.com 形式で入力してください"
        )
    return errors


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Configure .env for YuiGateway")
    p.add_argument("--tenant-id")
    p.add_argument("--client-id")
    p.add_argument("--client-secret")
    p.add_argument("--endpoint", dest="azure_openai_endpoint")
    p.add_argument(
        "--scope",
        default="https://cognitiveservices.azure.com/.default",
    )
    p.add_argument("--non-interactive", action="store_true")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing values")
    p.add_argument("--no-backup", action="store_true")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    _maybe_copy_template(no_backup=args.no_backup)

    # Seed defaults from existing env file if present
    existing_lines = _read_env_lines(ENV_FILE)
    existing_map: Dict[str, str] = {}
    for line in existing_lines:
        if not line or line.strip().startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            existing_map[k.strip()] = v.strip()

    defaults = {
        "TENANT_ID": args.tenant_id or existing_map.get("TENANT_ID") or _detect_tenant_from_azure_cli() or "",
        "CLIENT_ID": args.client_id or existing_map.get("CLIENT_ID", ""),
        "CLIENT_SECRET": args.client_secret or existing_map.get("CLIENT_SECRET", ""),
        "SCOPE": args.scope or existing_map.get("SCOPE", "https://cognitiveservices.azure.com/.default"),
        "AZURE_OPENAI_ENDPOINT": args.azure_openai_endpoint or existing_map.get("AZURE_OPENAI_ENDPOINT", ""),
    }

    if args.non_interactive:
        values = defaults
    else:
        print("YuiGateway .env セットアップを開始します。空 Enter で既定値を使用します。\n")
        values = {
            "TENANT_ID": _prompt("TENANT_ID", default=defaults["TENANT_ID"]),
            "CLIENT_ID": _prompt("CLIENT_ID", default=defaults["CLIENT_ID"]),
            "CLIENT_SECRET": _prompt("CLIENT_SECRET", secret=True, default=defaults["CLIENT_SECRET"]),
            "SCOPE": _prompt("SCOPE", default=defaults["SCOPE"] or "https://cognitiveservices.azure.com/.default"),
            "AZURE_OPENAI_ENDPOINT": _prompt(
                "AZURE_OPENAI_ENDPOINT", default=defaults["AZURE_OPENAI_ENDPOINT"]
            ),
        }

    errors = _validate(values)
    if errors:
        print("設定値に問題があります:\n - " + "\n - ".join(errors))
        return 2

    # Prepare updates map; if not overwrite, keep existing when present
    updates: Dict[str, str] = {}
    for k in REQUIRED_KEYS:
        if not args.overwrite and k in existing_map and existing_map[k]:
            updates[k] = existing_map[k]
        else:
            updates[k] = values.get(k, "")

    bak = _backup_env(no_backup=args.no_backup)
    new_lines = _update_env_lines(existing_lines, updates)
    _write_env_lines(ENV_FILE, new_lines)

    print(".env を更新しました:")
    printable = {
        "TENANT_ID": values["TENANT_ID"],
        "CLIENT_ID": values["CLIENT_ID"],
        "CLIENT_SECRET": _mask(values["CLIENT_SECRET"]),
        "SCOPE": values["SCOPE"],
        "AZURE_OPENAI_ENDPOINT": values["AZURE_OPENAI_ENDPOINT"],
    }
    for k, v in printable.items():
        print(f" - {k}: {v}")
    if bak:
        print(f"バックアップ作成: {bak}")
    print("\n完了しました。YuiGateway を起動できます。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
