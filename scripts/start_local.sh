#!/bin/bash
# YuiGateway ローカル起動スクリプト
# .env ファイルが必要（.env.template を参照）

set -e

# .env ファイルの存在確認
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    echo "Please copy .env.template to .env and configure it"
    exit 1
fi

# Uvicorn でアプリケーションを起動
echo "Starting YuiGateway..."
uvicorn gateway.routes:app --reload --host 0.0.0.0 --port 8000
