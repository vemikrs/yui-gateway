#!/bin/bash
# YuiGateway ローカル起動スクリプト
# .env ファイルが必要（.env.template を参照）

set -e

# .env が無い場合の自動化
if [ ! -f .env ]; then
    echo ".env が見つかりません。"
    if [ "${AUTO_PROVISION}" = "1" ]; then
        echo "AUTO_PROVISION=1 のため SDK ベースで自動プロビジョニングを実行します。"
        if command -v poetry >/dev/null 2>&1; then
            poetry run python scripts/provision_env.py || {
                echo "自動プロビジョニングに失敗しました。scripts/setup_env.py を対話実行します。";
                poetry run python scripts/setup_env.py || exit 1;
            }
        elif [ -x .venv/bin/python ]; then
            .venv/bin/python scripts/provision_env.py || {
                echo "自動プロビジョニングに失敗しました。scripts/setup_env.py を対話実行します。";
                .venv/bin/python scripts/setup_env.py || exit 1;
            }
        else
            python3 scripts/provision_env.py || {
                echo "自動プロビジョニングに失敗しました。scripts/setup_env.py を対話実行します。";
                python3 scripts/setup_env.py || exit 1;
            }
        fi
    else
        echo "AUTO_PROVISION=1 を指定すると SDK ベースで自動プロビジョニングを行います。"
        echo "対話式で .env を作成します。"
        if command -v poetry >/dev/null 2>&1; then
            poetry run python scripts/setup_env.py || exit 1
        elif [ -x .venv/bin/python ]; then
            .venv/bin/python scripts/setup_env.py || exit 1
        else
            python3 scripts/setup_env.py || exit 1
        fi
    fi
fi

# Uvicorn でアプリケーションを起動
echo "Starting YuiGateway..."
uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000
